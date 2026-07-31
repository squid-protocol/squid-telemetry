import os
import requests
import sqlite3
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- CONFIGURATION ---
TARGET_REPOS = [
    "squid-protocol/gitgalaxy",
    "squid-protocol/language-crucible",
    "squid-protocol/cobol_to_java_examples",
    "squid-protocol/teaching-portfolio",
    "squid-protocol/meow-turtle",
    "squid-protocol/sorting_evolution_algorithm"
]

DB_NAME = "traffic_metrics.db"
GITHUB_PAT = os.environ.get("TRAFFIC_READ_PAT")
GITLAB_PAT = os.environ.get("GITLAB_READ_PAT")

if not GITHUB_PAT:
    raise ValueError("TRAFFIC_READ_PAT environment variable is missing!")

HEADERS = {
    "Authorization": f"token {GITHUB_PAT}",
    "Accept": "application/vnd.github.v3+json"
}

GITLAB_HEADERS = {
    "Authorization": f"Bearer {GITLAB_PAT}",
    "Content-Type": "application/json"
} if GITLAB_PAT else {}

def init_db(conn):
    """Forges the SQLite schema if it does not exist."""
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_views (
            repo_name TEXT,
            date TEXT,
            total_views INTEGER,
            unique_visitors INTEGER,
            UNIQUE(repo_name, date)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_clones (
            repo_name TEXT,
            date TEXT,
            total_clones INTEGER,
            unique_cloners INTEGER,
            UNIQUE(repo_name, date)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referring_sites (
            repo_name TEXT,
            fetch_date TEXT,
            site TEXT,
            total_views INTEGER,
            unique_visitors INTEGER,
            UNIQUE(repo_name, fetch_date, site)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS popular_content (
            repo_name TEXT,
            fetch_date TEXT,
            path TEXT,
            total_views INTEGER,
            unique_visitors INTEGER,
            UNIQUE(repo_name, fetch_date, path)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pypi_downloads (
            repo_name TEXT,
            date TEXT,
            downloads INTEGER,
            UNIQUE(repo_name, date)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gitlab_catalog_usage (
            repo_name TEXT,
            date TEXT,
            usage_count_30_days INTEGER,
            UNIQUE(repo_name, date)
        )
    """)

    # Human-discovery signal: GitHub's own repo-level counters. Unlike clones/views
    # (14-day rolling windows), these are point-in-time snapshots, so we store one
    # row per day and let the graph layer read them as a simple time series.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repo_stats (
            repo_name TEXT,
            date TEXT,
            stars INTEGER,
            forks INTEGER,
            open_issues INTEGER,
            UNIQUE(repo_name, date)
        )
    """)

    # Production-integration signal: how many distinct external repos reference
    # gitgalaxy's GitHub Action (`uses: squid-protocol/gitgalaxy`) in a workflow
    # file. There's no GitHub Marketplace listing for this action, so code search
    # is the only passive way to observe adoption -- see fetch_and_store() for
    # the query and its known limitations.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_adoption (
            date TEXT,
            matching_files INTEGER,
            unique_repos INTEGER,
            UNIQUE(date)
        )
    """)
    conn.commit()

def _fetch_all_pages(url, headers, params=None):
    """Fetches every page of a paginated GitHub REST list endpoint."""
    results = []
    page = 1
    while True:
        page_params = dict(params or {})
        page_params.update({"per_page": 100, "page": page})
        resp = requests.get(url, headers=headers, params=page_params)
        if resp.status_code != 200:
            logging.error(f"Failed to fetch page {page} of {url}: {resp.status_code} - {resp.text}")
            break
        batch = resp.json()
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results

def _cumulative_by_date(event_dates, start_date, end_date):
    """
    Given a list of 'YYYY-MM-DD' event dates (e.g. one per star/fork), returns
    {date: running_total} for every calendar day from start_date to end_date
    inclusive. This is the one place cumulative math is actually valid here:
    each event (a star, a fork) is a distinct, non-repeatable action by
    construction -- unlike "unique cloners", there's no repeat-visitor
    double-counting risk to worry about.
    """
    event_dates = sorted(event_dates)
    result = {}
    idx = 0
    count = 0
    d = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    while d <= end:
        d_str = d.strftime('%Y-%m-%d')
        while idx < len(event_dates) and event_dates[idx] <= d_str:
            count += 1
            idx += 1
        result[d_str] = count
        d += timedelta(days=1)
    return result

def fetch_and_store(conn):
    """Hits the GitHub API and upserts the 14-day sliding window data."""
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')

    for repo in TARGET_REPOS:
        logging.info(f"Scraping telemetry for {repo}...")

        # 0. Repo Stats (Stars/Forks/Open Issues) -- human-discovery signal.
        # Unlike unique_cloners/unique_visitors, stars and forks are each a
        # single, non-repeatable action with GitHub's own timestamp attached
        # (starred_at / created_at) -- so instead of waiting weeks for daily
        # snapshots to build a trend, reconstruct the REAL historical curve
        # right now from every current stargazer's/fork's own timestamp, and
        # backfill every day since the first one. Re-derived from the live
        # list on every run, so it's self-correcting (a missed day heals
        # itself; an unstarred repo's historical curve adjusts down too,
        # which is more honest than a frozen snapshot would be).
        #
        # Known caveat: this only sees CURRENTLY-EXISTING stars/forks -- a
        # star or fork that was later removed/deleted doesn't appear in
        # today's list at all, so historical peaks before a removal are
        # invisible. Not fixable without GitHub retaining removal events,
        # which it doesn't expose.
        url_repo = f"https://api.github.com/repos/{repo}"
        resp_repo = requests.get(url_repo, headers=HEADERS)
        if resp_repo.status_code != 200:
            logging.error(f"Failed to fetch repo stats for {repo}: {resp_repo.status_code} - {resp_repo.text}")
            continue

        repo_data = resp_repo.json()
        open_issues = repo_data.get('open_issues_count', 0)

        star_headers = {**HEADERS, "Accept": "application/vnd.github.star+json"}
        stargazers = _fetch_all_pages(f"{url_repo}/stargazers", star_headers)
        forks = _fetch_all_pages(f"{url_repo}/forks", HEADERS, params={"sort": "oldest"})
        star_dates = [s['starred_at'][:10] for s in stargazers if 'starred_at' in s]
        fork_dates = [f['created_at'][:10] for f in forks if 'created_at' in f]

        if star_dates or fork_dates:
            earliest = min(star_dates + fork_dates)
            stars_by_date = _cumulative_by_date(star_dates, earliest, today_str)
            forks_by_date = _cumulative_by_date(fork_dates, earliest, today_str)
            for d in sorted(set(stars_by_date) | set(forks_by_date)):
                cursor.execute("""
                    INSERT OR REPLACE INTO repo_stats (repo_name, date, stars, forks, open_issues)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    repo, d,
                    stars_by_date.get(d, 0),
                    forks_by_date.get(d, 0),
                    open_issues if d == today_str else None,
                ))
        else:
            # No stars/forks at all (or the paginated fetch failed) -- fall
            # back to just today's snapshot from the repo endpoint itself.
            cursor.execute("""
                INSERT OR REPLACE INTO repo_stats (repo_name, date, stars, forks, open_issues)
                VALUES (?, ?, ?, ?, ?)
            """, (
                repo, today_str,
                repo_data.get('stargazers_count', 0),
                repo_data.get('forks_count', 0),
                open_issues,
            ))

        # 1. Traffic Views
        url_views = f"https://api.github.com/repos/{repo}/traffic/views"
        resp_views = requests.get(url_views, headers=HEADERS)
        if resp_views.status_code == 200:
            for view in resp_views.json().get('views', []):
                date_str = view['timestamp'][:10]
                cursor.execute("""
                    INSERT OR REPLACE INTO traffic_views (repo_name, date, total_views, unique_visitors)
                    VALUES (?, ?, ?, ?)
                """, (repo, date_str, view['count'], view['uniques']))
        else:
            logging.error(f"Failed to fetch views for {repo}: {resp_views.status_code} - {resp_views.text}")

        # 2. Traffic Clones
        url_clones = f"https://api.github.com/repos/{repo}/traffic/clones"
        resp_clones = requests.get(url_clones, headers=HEADERS)
        if resp_clones.status_code == 200:
            for clone in resp_clones.json().get('clones', []):
                date_str = clone['timestamp'][:10]
                cursor.execute("""
                    INSERT OR REPLACE INTO traffic_clones (repo_name, date, total_clones, unique_cloners)
                    VALUES (?, ?, ?, ?)
                """, (repo, date_str, clone['count'], clone['uniques']))
        else:
            logging.error(f"Failed to fetch clones for {repo}: {resp_clones.status_code} - {resp_clones.text}")

        # 3. Referring Sites
        url_referrers = f"https://api.github.com/repos/{repo}/traffic/popular/referrers"
        resp_refs = requests.get(url_referrers, headers=HEADERS)
        if resp_refs.status_code == 200:
            for ref in resp_refs.json():
                cursor.execute("""
                    INSERT OR REPLACE INTO referring_sites (repo_name, fetch_date, site, total_views, unique_visitors)
                    VALUES (?, ?, ?, ?, ?)
                """, (repo, today_str, ref['referrer'], ref['count'], ref['uniques']))
        else:
            logging.error(f"Failed to fetch referrers for {repo}: {resp_refs.status_code} - {resp_refs.text}")

        # 4. Popular Content (Paths)
        url_paths = f"https://api.github.com/repos/{repo}/traffic/popular/paths"
        resp_paths = requests.get(url_paths, headers=HEADERS)
        if resp_paths.status_code == 200:
            for path_data in resp_paths.json():
                cursor.execute("""
                    INSERT OR REPLACE INTO popular_content (repo_name, fetch_date, path, total_views, unique_visitors)
                    VALUES (?, ?, ?, ?, ?)
                """, (repo, today_str, path_data['path'], path_data['count'], path_data['uniques']))
        else:
            logging.error(f"Failed to fetch paths for {repo}: {resp_paths.status_code} - {resp_paths.text}")

        # 5. PyPI Downloads
        package_name = repo.split('/')[-1]
        url_pypi = f"https://pypistats.org/api/packages/{package_name}/overall"
        resp_pypi = requests.get(url_pypi)
        if resp_pypi.status_code == 200:
            pypi_data = resp_pypi.json().get('data', [])
            for row in pypi_data:
                # Filter to only capture clean downloads without mirrors
                if row.get('category') == 'without_mirrors':
                    cursor.execute("""
                        INSERT OR REPLACE INTO pypi_downloads (repo_name, date, downloads)
                        VALUES (?, ?, ?)
                    """, (repo, row['date'], row['downloads']))
        elif resp_pypi.status_code == 404:
            logging.info(f"No PyPI package found for {package_name}, skipping PyPI stats.")
        else:
            logging.error(f"Failed to fetch PyPI stats for {package_name}: {resp_pypi.status_code} - {resp_pypi.text}")

        # 6. GitLab CI/CD Catalog Usage (GraphQL)
        # BUG FIX: this used to also require `GITLAB_PAT` before even attempting the
        # fetch, but ciCatalogResource is a public query for a public catalog resource
        # -- confirmed working with zero auth via a bare curl. That guard silently
        # skipped this entire block (no error logged) whenever the PAT secret was
        # unset/expired, which is exactly what happened: gitlab_catalog_usage had
        # ZERO rows despite this code existing. Still send the PAT when present
        # (GITLAB_HEADERS already handles that), since it likely raises the rate
        # limit, but don't require it.
        if repo == "squid-protocol/gitgalaxy":
            gitlab_path = "squid-protocol1/gitgalaxy"
            query = """
            query getCiCatalogResourceComponents($fullPath: ID!) {
              ciCatalogResource(fullPath: $fullPath) {
                last30DayUsageCount
              }
            }
            """
            url_gitlab = "https://gitlab.com/api/graphql"

            def _query_gitlab(headers):
                resp = requests.post(
                    url_gitlab,
                    headers=headers,
                    json={"query": query, "variables": {"fullPath": gitlab_path}}
                )
                if resp.status_code != 200:
                    logging.error(f"GitLab usage fetch for {gitlab_path} returned HTTP {resp.status_code}: {resp.text}")
                    return None
                body = resp.json()
                # GraphQL endpoints commonly return HTTP 200 even when the query
                # itself failed (auth problems, resolver errors, etc.), with the
                # actual problem living in a top-level "errors" array instead of
                # the status code -- log it explicitly rather than silently
                # falling through to "no data".
                if body.get('errors'):
                    logging.error(f"GitLab GraphQL errors for {gitlab_path}: {body['errors']}")
                return body.get('data', {}).get('ciCatalogResource')

            # BUG FIX: a prior run of this scraper (2026-07-31, production) sent
            # the authenticated request and got back HTTP 200 with a NULL
            # ciCatalogResource -- silently skipped, no log line at all, because
            # this branch previously had no logging for that case. Confirmed via
            # a bare unauthenticated curl that this specific query works fine
            # against this public catalog resource with zero auth, so if the
            # (possibly stale/wrong-scoped) PAT's request comes back empty, retry
            # anonymously before giving up -- known-good fallback, not a guess.
            gl_data = _query_gitlab(GITLAB_HEADERS) if GITLAB_HEADERS else None
            if not gl_data:
                if GITLAB_HEADERS:
                    logging.info(f"Authenticated GitLab query for {gitlab_path} returned no data; retrying anonymously.")
                gl_data = _query_gitlab({})

            if gl_data:
                usage_count = gl_data.get('last30DayUsageCount', 0)
                cursor.execute("""
                    INSERT OR REPLACE INTO gitlab_catalog_usage (repo_name, date, usage_count_30_days)
                    VALUES (?, ?, ?)
                """, (repo, today_str, usage_count))
            else:
                logging.error(f"GitLab usage for {gitlab_path} unavailable via both authenticated and anonymous query.")

    conn.commit()
    logging.info("Telemetry successfully committed to SQLite.")

def fetch_action_adoption(conn):
    """
    Production-integration signal for the GitHub Action: gitgalaxy isn't listed
    on the GitHub Marketplace, so there's no install count to read. Code search
    for `uses: squid-protocol/gitgalaxy` in workflow files is the only passive
    way to observe how many external repos have wired it into CI.

    Known limitations (documented, not solved -- see squid-telemetry's README):
    - Only searches each matching repo's default branch, and only indexes
      files under 384 KB (irrelevant here, workflow files are tiny).
    - The search term is the bare "owner/repo" string scoped to
      `.github/workflows`, not a strict `uses:`-prefixed match -- GitHub's code
      search tokenizes on punctuation, so an exact `uses: X` phrase match isn't
      reliable. This slightly over-counts (would match a comment mentioning the
      string) but is a reasonable proxy; `matching_files` (raw) and
      `unique_repos` (deduped by repository) are both stored so a future pass
      can tighten the query without losing the raw signal.
    - Capped at the API's first page (100 results) -- fine at gitgalaxy's
      current adoption scale; revisit with pagination if it's ever maxed out.
    """
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')

    url_search = "https://api.github.com/search/code"
    params = {"q": '"squid-protocol/gitgalaxy" path:.github/workflows', "per_page": 100}
    resp = requests.get(url_search, headers=HEADERS, params=params)

    if resp.status_code == 200:
        data = resp.json()
        items = data.get("items", [])
        unique_repos = len({item["repository"]["full_name"] for item in items})
        cursor.execute("""
            INSERT OR REPLACE INTO action_adoption (date, matching_files, unique_repos)
            VALUES (?, ?, ?)
        """, (today_str, data.get("total_count", len(items)), unique_repos))
        conn.commit()
    else:
        logging.error(f"Failed to fetch Action adoption: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    conn = sqlite3.connect(DB_NAME)
    init_db(conn)
    fetch_and_store(conn)
    fetch_action_adoption(conn)
    conn.close()
