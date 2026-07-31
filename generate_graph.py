#!/usr/bin/env python3
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import requests

def generate_cumulative_graph(db_path: str, output_path: str):
    # 1. Connect to the database and extract the daily totals
    conn = sqlite3.connect(db_path)
    
    # BUG FIX: the GitHub component used to sum `unique_cloners` (a genuinely
    # deduplicated daily count) cumulatively -- but summing daily uniques
    # across days double-counts anyone who cloned on more than one day, since
    # GitHub's per-day uniqueness aggregate retains no cross-day identity to
    # de-overlap against (same repeat-visitor inflation documented on the
    # human-vs-CI chart). Switched to `total_clones` (raw clone-request
    # events, already collected, unused until now) so all three sources --
    # PyPI downloads, GitHub clones, GitLab catalog usage -- are now
    # consistently "distribution activity volume", not a mix of unique-headcount
    # and raw-event semantics. This chart was never meant to measure
    # uniqueness (see the human-vs-CI chart for that); now it's honestly
    # scoped to volume throughout, matching its own title.
    query = """
        WITH combined_traffic AS (
            -- 1. Baseline Repositories (Aggregated Totals)
            SELECT repo_name, date, downloads as volume FROM pypi_downloads WHERE repo_name != 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT repo_name, date, total_clones as volume FROM traffic_clones WHERE repo_name != 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT repo_name, date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (PARTITION BY repo_name ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name != 'squid-protocol/gitgalaxy'

            UNION ALL

            -- 2. GitGalaxy Total
            SELECT 'gitgalaxy_total' as repo_name, date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_total' as repo_name, date, total_clones as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_total' as repo_name, date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name = 'squid-protocol/gitgalaxy'

            UNION ALL

            -- 3. GitGalaxy Components
            SELECT 'gitgalaxy_pypi' as repo_name, date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_github' as repo_name, date, total_clones as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_gitlab' as repo_name, date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name = 'squid-protocol/gitgalaxy'
        )
        SELECT repo_name, date, SUM(volume) as daily_downloads
        FROM combined_traffic
        GROUP BY repo_name, date
        ORDER BY date ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 2. Process the data
    if df.empty:
        print("No traffic data found in the database.")
        return

    df['date'] = pd.to_datetime(df['date'])
    
    # Pivot the data without filling NaN with 0. 
    # This ensures pandas .cumsum() naturally starts drawing each line 
    # exactly at its respective first date of collected data.
    pivot_df = df.pivot(index='date', columns='repo_name', values='daily_downloads')
    
    # Calculate cumulative sum for all series
    cumulative_df = pivot_df.cumsum()

    # 3. Render the Professional Graph
    import matplotlib.dates as mdates
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot target total first for top legend ordering
    if 'gitgalaxy_total' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['gitgalaxy_total'], 
                color='red', linewidth=3, label='GitGalaxy (Total)', zorder=10)
                
    # Plot GitGalaxy component lines 
    if 'gitgalaxy_github' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['gitgalaxy_github'], 
                color='#1f77b4', linewidth=2, linestyle='--', label='GitGalaxy (GitHub)', zorder=9)
    if 'gitgalaxy_pypi' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['gitgalaxy_pypi'], 
                color='#ff7f0e', linewidth=2, linestyle='--', label='GitGalaxy (PyPI)', zorder=9)
    if 'gitgalaxy_gitlab' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['gitgalaxy_gitlab'], 
                color='#9467bd', linewidth=2, linestyle='--', label='GitGalaxy (GitLab)', zorder=9)
                
    # Plot language-crucible in green
    if 'squid-protocol/language-crucible' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['squid-protocol/language-crucible'], 
                color='green', linewidth=2.5, label='language-crucible', zorder=8)
    
    # Plot the remaining negative controls in light gray as a grouped background layer
    added_baseline = False
    for repo in cumulative_df.columns:
        if repo not in ['gitgalaxy_total', 'gitgalaxy_github', 'gitgalaxy_pypi', 'gitgalaxy_gitlab', 'squid-protocol/language-crucible']:
            if not added_baseline:
                ax.plot(cumulative_df.index, cumulative_df[repo], color='lightgray', 
                        alpha=0.8, linewidth=1.5, label='Baseline Repo Examples', zorder=1)
                added_baseline = True
            else:
                ax.plot(cumulative_df.index, cumulative_df[repo], color='lightgray', 
                        alpha=0.8, linewidth=1.5, zorder=1)
    
    # Formatting the chart
    # NOTE: deliberately not labeled "Unique Fetches" -- PyPI's without_mirrors
    # count is raw download EVENTS (no dedup possible, PyPI's public dataset
    # has no identity to dedup against), GitHub's total_clones is likewise a
    # raw clone-request event count (see the query comment above for why this
    # replaced unique_cloners), and only GitLab's usage_count_30_days is
    # genuinely deduplicated (per-project, per GitLab's own docs). Summing
    # them is a useful combined *volume* signal, but not a "unique adopters"
    # count -- see the separate human-vs-CI chart for that story instead.
    ax.set_title("Cumulative Distribution Volume of GitGalaxy (PyPI Without Mirrors)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Combined Distribution Volume", fontsize=12, labelpad=10)
    
    # Format X-axis dates to Year-Month (YYYY-MM)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    # Add a legend
    ax.legend(loc='upper left', fontsize=10)
    
    # Clean up the bounding box
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#333333')
    ax.spines['bottom'].set_color('#333333')
    
    ax.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    
    # 4. Save the artifact
    plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")

def generate_conversion_funnel(db_path: str, output_path: str):
    conn = sqlite3.connect(db_path)
    query = """
        WITH views AS (
            SELECT date, unique_visitors as views
            FROM traffic_views
            WHERE repo_name = 'squid-protocol/gitgalaxy'
        ),
        downloads AS (
            SELECT date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT date, total_clones as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name = 'squid-protocol/gitgalaxy'
        ),
        agg_downloads AS (
            SELECT date, SUM(volume) as total_downloads
            FROM downloads
            GROUP BY date
        )
        SELECT v.date, v.views, COALESCE(d.total_downloads, 0) as downloads
        FROM views v
        LEFT JOIN agg_downloads d ON v.date = d.date
        ORDER BY v.date DESC LIMIT 14;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty: return
    
    df = df.sort_values('date') 
    df['date_dt'] = pd.to_datetime(df['date'])
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Render both datasets as plain lines (no point markers -- the per-point
    # numeric labels below already mark each value, a redundant dot on top
    # just adds clutter).
    # NOTE: "downloads" here is a combined volume (GitHub clone events + PyPI
    # download events + GitLab unique-project usage), not a uniformly
    # deduplicated count -- see generate_cumulative_graph()'s own note.
    ax.plot(df['date_dt'], df['views'], color='#4682B4', linewidth=2, label='Unique Profile Views (Intent)')
    ax.plot(df['date_dt'], df['downloads'], color='#00008B', linewidth=2, label='Combined Fetch Volume (Execution)')
    
    # Calculate offset for labels based on the max value in the graph
    y_offset = df[['views', 'downloads']].max().max() * 0.02
    
    # Add numerical data labels directly above each point
    for x, y in zip(df['date_dt'], df['views']):
        ax.text(x, y + y_offset, f'{int(y)}', ha='center', va='bottom', fontsize=9, color='#4682B4', fontweight='bold')
    for x, y in zip(df['date_dt'], df['downloads']):
        ax.text(x, y + y_offset, f'{int(y)}', ha='center', va='bottom', fontsize=9, color='#00008B', fontweight='bold')
    
    ax.set_title("GitGalaxy Conversion Funnel (14-Day Rolling)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Count", fontsize=12, labelpad=10)

    import matplotlib.dates as mdates
    # BUG FIX: '%Y-%m' (month-only) on a 14-day window means every single tick
    # renders as the same "2026-07" label -- useless for a chart whose whole
    # point is showing day-to-day movement. Day-level format instead.
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45)
    
    ax.legend(loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")
    
def generate_discovery_engine(db_path: str, output_path: str):
    conn = sqlite3.connect(db_path)
    query = """
        SELECT fetch_date as date, site, SUM(unique_visitors) as unique_visitors 
        FROM referring_sites 
        WHERE repo_name = 'squid-protocol/gitgalaxy' 
          AND fetch_date IN (SELECT DISTINCT fetch_date FROM referring_sites WHERE repo_name = 'squid-protocol/gitgalaxy' ORDER BY fetch_date DESC LIMIT 14)
        GROUP BY date, site
        ORDER BY date ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty: return
    
    df['date_dt'] = pd.to_datetime(df['date'])
    pivot_df = df.pivot(index='date_dt', columns='site', values='unique_visitors').fillna(0)
    
    # Filter to top 5 performing channels to keep the graph readable
    top_sites = pivot_df.sum().nlargest(5).index.tolist()

    # PINNED_CHANNELS: always shown regardless of raw-volume rank, because
    # they answer a DIFFERENT question than "which referrer sends the most
    # traffic" -- github-help-wanted.com is GitHub's own contributor-
    # recruitment surface (its "help wanted" listings), so it's a signal for
    # "are we attracting potential CONTRIBUTORS specifically", not general
    # discovery volume. Currently ~15 unique visitors total -- real, but
    # below the top-5-by-volume cutoff (Bing/Google/reddit dominate by raw
    # count), so it would otherwise never appear here at all.
    PINNED_CHANNELS = ['github-help-wanted.com']
    for channel in PINNED_CHANNELS:
        if channel in pivot_df.columns and channel not in top_sites:
            top_sites.append(channel)
    pivot_df = pivot_df[top_sites]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    for site in pivot_df.columns:
        ax.plot(pivot_df.index, pivot_df[site], linewidth=2, label=site)

    ax.set_title("Top Discovery Channels (14-Day Rolling Timeline)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Unique Visitors", fontsize=12, labelpad=10)

    import matplotlib.dates as mdates
    # Day-level format -- see conversion_funnel's identical fix above;
    # month-only was unreadable on a 14-day window.
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45)
    
    # Push legend outside the plot to avoid overlapping the data lines
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")
def generate_feature_heatmap(db_path: str, output_path: str):
    conn = sqlite3.connect(db_path)
    query = """
        SELECT fetch_date as date, path, SUM(unique_visitors) as unique_visitors 
        FROM popular_content 
        WHERE repo_name = 'squid-protocol/gitgalaxy' 
          AND fetch_date IN (SELECT DISTINCT fetch_date FROM popular_content WHERE repo_name = 'squid-protocol/gitgalaxy' ORDER BY fetch_date DESC LIMIT 14)
          AND path NOT LIKE '%/issues%'
          AND path NOT LIKE '%/pulls%'
          AND path NOT LIKE '%/pulse%'
          AND path NOT LIKE '%/graphs%'
          AND path NOT LIKE '%/milestone%'
          AND path != '/squid-protocol/gitgalaxy'
        GROUP BY date, path
        ORDER BY date ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty: return
    
    # Strip the verbose GitHub domains to make the chart labels clean
    df['clean_path'] = df['path'].apply(lambda x: x.replace('/squid-protocol/gitgalaxy/tree/main/', '')
                                                  .replace('/squid-protocol/gitgalaxy/blob/main/', '')
                                                  .replace('/squid-protocol/gitgalaxy', '/ (Root)'))

    # BUG FIX: a deep file path (e.g.
    # "gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py") was
    # still the FULL relative path after the repo-prefix strip above -- long
    # enough to blow out the legend's width on its own. Collapse anything
    # with more than 2 path segments down to just "parent-dir/filename",
    # prefixed with an ellipsis so it still reads as "somewhere deeper", not
    # like the whole path.
    def _shorten_path(p):
        parts = p.strip('/').split('/')
        return p if len(parts) <= 2 else '.../' + '/'.join(parts[-2:])
    df['clean_path'] = df['clean_path'].apply(_shorten_path)

    df['date_dt'] = pd.to_datetime(df['date'])
    pivot_df = df.pivot(index='date_dt', columns='clean_path', values='unique_visitors').fillna(0)

    # Filter to top 5 paths to keep the graph readable
    top_paths = pivot_df.sum().nlargest(5).index
    pivot_df = pivot_df[top_paths]

    fig, ax = plt.subplots(figsize=(10, 6))
    for path in pivot_df.columns:
        ax.plot(pivot_df.index, pivot_df[path], linewidth=2, label=path)

    ax.set_title("Feature Intent Patterns (14-Day Rolling Timeline)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Unique Visitors", fontsize=12, labelpad=10)

    import matplotlib.dates as mdates
    # Day-level format -- see conversion_funnel's identical fix above;
    # month-only was unreadable on a 14-day window.
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45)
    
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")
    
def generate_release_correlation(db_path: str, output_path: str):
    # 1. Fetch dynamic release history directly from PyPI
    resp = requests.get("https://pypi.org/pypi/gitgalaxy/json")
    daily_versions = {}
    
    if resp.status_code == 200:
        data = resp.json()
        releases_raw = data.get("releases", {})
        
        for version, uploads in releases_raw.items():
            if not uploads:
                continue
            # Extract the YYYY-MM-DD from the upload_time
            upload_date = uploads[0]['upload_time'].split('T')[0]
            if upload_date not in daily_versions:
                daily_versions[upload_date] = []
            daily_versions[upload_date].append(version)
            
    # 2. Condense multiple patches on the same day to the highest version
    releases = {}
    def version_tuple(v):
        return [int(x) if x.isdigit() else x for x in v.split('.')]

    for date_str, v_list in daily_versions.items():
        v_list.sort(key=version_tuple)
        releases[date_str] = f"v{v_list[-1]}"

    # 2b. BUG FIX: step 2 only condensed releases landing on the SAME day --
    # but active patch cadences ship a new version every day or two (e.g.
    # v2.3.9, v2.3.12, v2.3.17, v2.3.20 within one week), each on a
    # DIFFERENT day, so each still got its own vertical line + rotated text
    # label, and those labels overlapped into an unreadable pile (confirmed
    # by rendering it). Collapse any run of releases within CLUSTER_DAYS of
    # the cluster's start into ONE label, shown at the cluster's last date
    # with the latest version reached -- still shows the real release
    # cadence, just not every single patch tick.
    CLUSTER_DAYS = 3
    sorted_release_dates = sorted(releases.keys(), key=pd.to_datetime)
    clustered_releases = {}
    cluster_start = cluster_last_date = None
    for date_str in sorted_release_dates:
        dt = pd.to_datetime(date_str)
        if cluster_start is None or (dt - cluster_start).days > CLUSTER_DAYS:
            cluster_start = dt
        cluster_last_date = date_str
        clustered_releases[cluster_start] = (date_str, releases[date_str])
    releases = {date_str: version for date_str, version in clustered_releases.values()}

    # 3. Query the aggregated daily fetches across all sources
    conn = sqlite3.connect(db_path)
    query = """
        WITH combined_traffic AS (
            SELECT date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT date, total_clones as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name = 'squid-protocol/gitgalaxy'
        )
        SELECT date, SUM(volume) as daily_downloads 
        FROM combined_traffic 
        GROUP BY date 
        ORDER BY date ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty: return

    # 4. Process data and calculate cumulative sum
    df['date_dt'] = pd.to_datetime(df['date'])
    df['cumulative_downloads'] = df['daily_downloads'].cumsum()
    
    # 5. Render the graph
    import matplotlib.dates as mdates
    fig, ax = plt.subplots(figsize=(14, 7))
    
    ax.plot(df['date_dt'], df['cumulative_downloads'], color='#4682B4', linewidth=3, label='Cumulative Distribution Volume')

    # Sort dates to calculate the 75% threshold for label placement
    sorted_dates = sorted(releases.keys())
    if sorted_dates:
        threshold_idx = int(len(sorted_dates) * 0.75)
        
        for i, date_str in enumerate(sorted_dates):
            version = releases[date_str]
            dt = pd.to_datetime(date_str)
            
            if not df.empty and dt >= df['date_dt'].min() and dt <= df['date_dt'].max():
                ax.axvline(x=dt, color='#ff7f0e', linestyle='--', linewidth=1.5, alpha=0.8)
                
                # If in the last 25% of releases, anchor text to the bottom to avoid the soaring line
                if i >= threshold_idx:
                    y_pos = ax.get_ylim()[1] * 0.05
                    va_align = 'bottom'
                else:
                    y_pos = ax.get_ylim()[1] * 0.95
                    va_align = 'top'
                    
                ax.text(dt, y_pos, version, rotation=90, color='#d62728', 
                        fontweight='bold', fontsize=9, va=va_align, ha='right',
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8))

    ax.set_title("GitGalaxy Cumulative Downloads vs. Release Cadence", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Combined Distribution Volume", fontsize=12, labelpad=10)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    # lower right, not upper left: the early release cluster's labels sit at
    # the top of the chart (near x-axis start), directly under where an
    # upper-left legend box would land -- confirmed by rendering it.
    ax.legend(loc='lower right')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle=':', alpha=0.4)
    
    plt.tight_layout()
    plt.savefig(output_path, format='png', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")

def generate_human_vs_ci_adoption(db_path: str, output_path: str):
    """
    One PNG, three subplots, for squid-protocol/gitgalaxy specifically:
    (1) stars/forks, (2) daily repo traffic (unique cloners/views), and
    (3) production/CI integration (GitLab CI/CD Catalog + GitHub Action
    code-search adoption). Split into three instead of the original two
    because stars/forks (cumulative, long real history) and cloners/views
    (daily, deliberately not cumulative) are different enough kinds of series
    that sharing one panel undersold both.

    Deliberately does NOT duplicate the existing cumulative-downloads chart --
    this is the "is anyone actually running this in CI" story, told with
    signals that chart can't show. Raw PyPI download volume stays out of all
    three panels: its scale (100s-1000s/day) dwarfs everything else here, and
    it already has its own dedicated chart.
    """
    conn = sqlite3.connect(db_path)

    human_stars = pd.read_sql_query(
        "SELECT date, stars, forks FROM repo_stats WHERE repo_name = 'squid-protocol/gitgalaxy' ORDER BY date",
        conn,
    )
    human_clones = pd.read_sql_query(
        "SELECT date, unique_cloners FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy' ORDER BY date",
        conn,
    )
    human_views = pd.read_sql_query(
        "SELECT date, unique_visitors FROM traffic_views WHERE repo_name = 'squid-protocol/gitgalaxy' ORDER BY date",
        conn,
    )
    ci_gitlab = pd.read_sql_query(
        "SELECT date, usage_count_30_days FROM gitlab_catalog_usage WHERE repo_name = 'squid-protocol/gitgalaxy' ORDER BY date",
        conn,
    )
    ci_action = pd.read_sql_query("SELECT date, unique_repos FROM action_adoption ORDER BY date", conn)
    conn.close()

    all_frames = (human_stars, human_clones, human_views, ci_gitlab, ci_action)
    if all(df.empty for df in all_frames):
        print("No human-vs-CI adoption data found in the database yet.")
        return

    for df in all_frames:
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])

    # The CI panel's two series (GitLab Catalog, Action adoption) are both
    # brand-new collections that may only have a handful of points -- with no
    # multi-point line to anchor a real range, matplotlib's autoscale can pick
    # an enormous, meaningless date span (observed: a single point rendered
    # against a 2024-2028 x-axis). Both panels share one explicit x-range
    # instead, spanning whichever series actually has the most history --
    # this also makes the two panels directly comparable at a glance, which
    # is the whole point of putting them side by side.
    all_dates = pd.concat([df['date'] for df in all_frames if not df.empty])
    date_min, date_max = all_dates.min(), all_dates.max()
    if date_min == date_max:
        date_min -= pd.Timedelta(days=7)
        date_max += pd.Timedelta(days=7)

    import matplotlib.dates as mdates
    from matplotlib.ticker import MaxNLocator

    # Font sizes bumped substantially across the board (title/axis/tick/legend)
    # per explicit request -- small multi-panel text was hard to read at the
    # size this normally renders at in a README. Bold applied to axis/tick/
    # legend text too (titles were already bold).
    TITLE_FS, AXIS_FS, TICK_FS, LEGEND_FS, SUPTITLE_FS = 24, 21, 18, 19, 28

    def _plot_series(ax, df, y_col, **kwargs):
        """
        Plain line, no markers -- except when a series has too few points
        for a line to render at all (a brand-new collection like GitLab
        Catalog/Action adoption may only have one point so far), in which
        case a single marker is the only way to show it exists at all.
        """
        if df.empty:
            return
        if len(df) == 1:
            kwargs.pop('linestyle', None)
            ax.plot(df['date'], df[y_col], marker='o', markersize=8, linestyle='', **kwargs)
        else:
            ax.plot(df['date'], df[y_col], **kwargs)

    def _anchor_zero_at(df, anchor_date):
        """
        If a series' own history starts after `anchor_date`, prepend a
        synthetic (anchor_date, 0-for-every-non-date-column) row so a lone,
        context-free point can render as an actual line instead of a dot with
        no story. This is a MODELING ASSUMPTION -- the metric was presumably
        0 before gitgalaxy existed / before we started tracking it, not
        something we actually measured back then -- documented here and in
        the README caption, not hidden. Used for GitLab Catalog usage, which
        has no known "this is when it changed" date the way Action adoption
        does (see the step-anchor just below) -- it's just been 0 throughout.
        """
        if df.empty or df['date'].min() <= anchor_date:
            return df
        anchor_row = {col: (anchor_date if col == 'date' else 0) for col in df.columns}
        return pd.concat([pd.DataFrame([anchor_row]), df], ignore_index=True)

    ci_gitlab = _anchor_zero_at(ci_gitlab, date_min)

    # GitHub Action adoption didn't grow gradually -- it jumped from 0 to its
    # current value on a SPECIFIC KNOWN date: gitgalaxy's own workflows
    # started referencing `uses: squid-protocol/gitgalaxy` on 2026-06-30 (per
    # the maintainer directly -- there's no API exposing "since when has this
    # workflow file contained this line", so this fact can't be derived, only
    # supplied). A straight line from date_min to today would misrepresent
    # this as smooth, gradual growth instead of the real step it was; drawn
    # with drawstyle='steps-post' below so it renders as an actual jump.
    GITGALAXY_ACTION_ADOPTION_DATE = pd.Timestamp('2026-06-30')
    if not ci_action.empty and ci_action['date'].min() > GITGALAXY_ACTION_ADOPTION_DATE > date_min:
        first_value = ci_action.iloc[0]['unique_repos']
        ci_action = pd.concat([
            pd.DataFrame([
                {'date': date_min, 'unique_repos': 0},
                {'date': GITGALAXY_ACTION_ADOPTION_DATE, 'unique_repos': first_value},
            ]),
            ci_action,
        ], ignore_index=True)
    else:
        ci_action = _anchor_zero_at(ci_action, date_min)

    # Matplotlib's built-in seaborn-derived stylesheet -- gives the clean
    # seaborn look without adding an actual seaborn dependency to the
    # pipeline's `pip install requests pandas matplotlib` step. "-white" (not
    # "-whitegrid"): no background gridlines, per explicit request. Scoped to
    # just this figure via the context manager so it doesn't change the
    # other 5 charts' existing look.
    with plt.style.context('seaborn-v0_8-white'):
        fig, (ax_stars, ax_traffic, ax_ci) = plt.subplots(1, 3, figsize=(22, 7))

        # --- Panel 1: Stars & Forks ---
        # Genuinely cumulative (reconstructed from each star's/fork's own
        # timestamp -- see scraper.py's _cumulative_by_date, a valid use of
        # cumulative math since each star/fork is a single non-repeatable
        # action, unlike cloners/views below).
        _plot_series(ax_stars, human_stars, 'stars', color='#f1c40f', linewidth=2.5, label='GitHub Stars')
        _plot_series(ax_stars, human_stars, 'forks', color='#e67e22', linewidth=2.5, label='GitHub Forks')
        ax_stars.set_title("Stars & Forks", fontsize=TITLE_FS, fontweight='bold')

        # --- Panel 2: Repository Traffic ---
        # Daily counts, NOT a rolling 14-day window despite the old chart's
        # label implying that -- GitHub's traffic API returns one entry per
        # calendar day, it just only exposes the trailing 14 days of them.
        # Deliberately NOT cumsum'd: summing daily "uniques" across days
        # double-counts anyone who visited on more than one day, since
        # GitHub's per-day uniqueness aggregate retains no cross-day identity
        # to de-overlap against -- there's no valid way to recover a true
        # cumulative-unique-visitor count from these aggregates.
        #
        # The flat gray segment marks the period before clones/views tracking
        # existed at all -- without it, this panel just has a big, unexplained
        # blank gap before the real lines start, which reads as broken rather
        # than "not tracked yet". No legend label (kept out of the legend
        # deliberately, per request, to keep it simple) -- the gray color
        # already reads as "not real data" against the colored lines.
        traffic_dates = pd.concat([df['date'] for df in (human_clones, human_views) if not df.empty])
        if not traffic_dates.empty and traffic_dates.min() > date_min:
            ax_traffic.plot([date_min, traffic_dates.min()], [0, 0], color='#999999', linewidth=2, zorder=1)
        _plot_series(ax_traffic, human_clones, 'unique_cloners', color='#1f77b4', linewidth=2, label='Unique Cloners')
        _plot_series(ax_traffic, human_views, 'unique_visitors', color='#4682B4', linewidth=1.5, linestyle='--',
                     label='Unique Profile Views')
        ax_traffic.set_title("Repository Traffic", fontsize=TITLE_FS, fontweight='bold')

        # --- Panel 3: Production / CI Integration ---
        # Legend labels kept to just the platform name -- all methodology
        # detail ("unique projects, 30d", "unique repos via code search")
        # lives in the README caption instead of the in-chart legend.
        # drawstyle='steps-post': both series are discrete counts that only
        # change when checked, not continuous quantities -- a step is the
        # honest rendering, not an interpolated slope between check-ins.
        _plot_series(ax_ci, ci_gitlab, 'usage_count_30_days', color='#9467bd', linewidth=2.5,
                     drawstyle='steps-post', label='GitLab')
        _plot_series(ax_ci, ci_action, 'unique_repos', color='#2ca02c', linewidth=2.5,
                     drawstyle='steps-post', label='GitHub Action')
        ax_ci.set_title("Production / CI Integration", fontsize=TITLE_FS, fontweight='bold')

        # No emoji anywhere in this figure: matplotlib's default DejaVu Sans
        # font has no emoji glyphs, so they'd render as empty tofu boxes on
        # the CI runner that generates this (confirmed by rendering it once).
        # Emoji are fine in the README's own markdown heading around the
        # embedded image, just not baked into the raster PNG itself.
        for ax in (ax_stars, ax_traffic, ax_ci):
            ax.set_xlabel("Date", fontsize=AXIS_FS, fontweight='bold')
            ax.set_ylabel("Count", fontsize=AXIS_FS, fontweight='bold')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%y'))
            # Cap both axes at ~4 ticks -- more legible at the bumped font
            # sizes, and less cluttered than a tick per week/every-few-units.
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=4))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
            ax.tick_params(axis='both', labelsize=TICK_FS)
            ax.tick_params(axis='x', rotation=45)
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontweight('bold')
            ax.grid(False)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.set_ylim(bottom=0)
            ax.set_xlim(date_min, date_max)
            ax.legend(loc='upper left', framealpha=0.9, prop={'size': LEGEND_FS, 'weight': 'bold'})

        # Simpler, plain-language title -- "Human Discovery vs. Production
        # Integration" reads like an internal analytics label, not something
        # a general reader parses at a glance.
        fig.suptitle("GitGalaxy: Discovery & Usage", fontsize=SUPTITLE_FS,
                     fontweight='bold', y=1.03)
        plt.tight_layout()
        plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")

if __name__ == "__main__":
    db = "traffic_metrics.db"
    generate_cumulative_graph(db, "cumulative_downloads.png")
    generate_conversion_funnel(db, "conversion_funnel.png")
    generate_discovery_engine(db, "discovery_channels.png")
    generate_feature_heatmap(db, "feature_intent.png")
    generate_release_correlation(db, "release_correlation.png")
    generate_human_vs_ci_adoption(db, "human_vs_ci_adoption.png")
