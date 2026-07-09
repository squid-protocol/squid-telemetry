import os
import requests
import sqlite3
import logging
from datetime import datetime

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
GITHUB_PAT = os.environ.get("GITHUB_PAT")

if not GITHUB_PAT:
    raise ValueError("GITHUB_PAT environment variable is missing!")

HEADERS = {
    "Authorization": f"token {GITHUB_PAT}",
    "Accept": "application/vnd.github.v3+json"
}

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
    conn.commit()

def fetch_and_store(conn):
    """Hits the GitHub API and upserts the 14-day sliding window data."""
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')

    for repo in TARGET_REPOS:
        logging.info(f"Scraping telemetry for {repo}...")
        
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

        # 3. Referring Sites
        url_referrers = f"https://api.github.com/repos/{repo}/traffic/popular/referrers"
        resp_refs = requests.get(url_referrers, headers=HEADERS)
        if resp_refs.status_code == 200:
            for ref in resp_refs.json():
                cursor.execute("""
                    INSERT OR REPLACE INTO referring_sites (repo_name, fetch_date, site, total_views, unique_visitors)
                    VALUES (?, ?, ?, ?, ?)
                """, (repo, today_str, ref['referrer'], ref['count'], ref['uniques']))

        # 4. Popular Content (Paths)
        url_paths = f"https://api.github.com/repos/{repo}/traffic/popular/paths"
        resp_paths = requests.get(url_paths, headers=HEADERS)
        if resp_paths.status_code == 200:
            for path_data in resp_paths.json():
                cursor.execute("""
                    INSERT OR REPLACE INTO popular_content (repo_name, fetch_date, path, total_views, unique_visitors)
                    VALUES (?, ?, ?, ?, ?)
                """, (repo, today_str, path_data['path'], path_data['count'], path_data['uniques']))

    conn.commit()
    logging.info("Telemetry successfully committed to SQLite.")
    
if __name__ == "__main__":
    conn = sqlite3.connect(DB_NAME)
    init_db(conn)
    fetch_and_store(conn)
    conn.close()