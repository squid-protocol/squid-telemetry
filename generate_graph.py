#!/usr/bin/env python3
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import requests

def generate_cumulative_graph(db_path: str, output_path: str):
    # 1. Connect to the database and extract the daily totals
    conn = sqlite3.connect(db_path)
    
    query = """
        WITH combined_traffic AS (
            -- 1. Baseline Repositories (Aggregated Totals)
            SELECT repo_name, date, downloads as volume FROM pypi_downloads WHERE repo_name != 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT repo_name, date, unique_cloners as volume FROM traffic_clones WHERE repo_name != 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT repo_name, date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (PARTITION BY repo_name ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name != 'squid-protocol/gitgalaxy'
            
            UNION ALL
            
            -- 2. GitGalaxy Total
            SELECT 'gitgalaxy_total' as repo_name, date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_total' as repo_name, date, unique_cloners as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_total' as repo_name, date, MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (ORDER BY date), 0)) as volume FROM gitlab_catalog_usage WHERE repo_name = 'squid-protocol/gitgalaxy'
            
            UNION ALL
            
            -- 3. GitGalaxy Components
            SELECT 'gitgalaxy_pypi' as repo_name, date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT 'gitgalaxy_github' as repo_name, date, unique_cloners as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
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
    ax.set_title("Cumulative Downloads of GitGalaxy (Without Mirrors)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Total Unique Fetches (GitHub, PyPI, GitLab)", fontsize=12, labelpad=10)
    
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
            SELECT date, unique_cloners as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
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
    
    # Render both datasets as lines with identical thicknesses
    ax.plot(df['date_dt'], df['views'], color='#4682B4', linewidth=2, marker='o', label='Unique Profile Views (Intent)')
    ax.plot(df['date_dt'], df['downloads'], color='#00008B', linewidth=2, marker='o', label='Unique Fetches (Execution)')
    
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
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
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
    top_sites = pivot_df.sum().nlargest(5).index
    pivot_df = pivot_df[top_sites]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    for site in pivot_df.columns:
        ax.plot(pivot_df.index, pivot_df[site], linewidth=2, marker='o', label=site)
        
    ax.set_title("Top Discovery Channels (14-Day Rolling Timeline)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Unique Visitors", fontsize=12, labelpad=10)
    
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
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
                                                  
    df['date_dt'] = pd.to_datetime(df['date'])
    pivot_df = df.pivot(index='date_dt', columns='clean_path', values='unique_visitors').fillna(0)
    
    # Filter to top 5 paths to keep the graph readable
    top_paths = pivot_df.sum().nlargest(5).index
    pivot_df = pivot_df[top_paths]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    for path in pivot_df.columns:
        ax.plot(pivot_df.index, pivot_df[path], linewidth=2, marker='o', label=path)
        
    ax.set_title("Feature Intent Patterns (14-Day Rolling Timeline)", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Unique Visitors", fontsize=12, labelpad=10)
    
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
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
    resp = requests.get("[https://pypi.org/pypi/gitgalaxy/json](https://pypi.org/pypi/gitgalaxy/json)")
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

    # 3. Query the aggregated daily fetches across all sources
    conn = sqlite3.connect(db_path)
    query = """
        WITH combined_traffic AS (
            SELECT date, downloads as volume FROM pypi_downloads WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT date, unique_cloners as volume FROM traffic_clones WHERE repo_name = 'squid-protocol/gitgalaxy'
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
    
    ax.plot(df['date_dt'], df['cumulative_downloads'], color='#4682B4', linewidth=3, label='Cumulative Unique Fetches')

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
    ax.set_ylabel("Total Cumulative Fetches", fontsize=12, labelpad=10)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    
    ax.legend(loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle=':', alpha=0.4)
    
    plt.tight_layout()
    plt.savefig(output_path, format='png', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")

if __name__ == "__main__":
    db = "traffic_metrics.db"
    generate_cumulative_graph(db, "cumulative_downloads.png")
    generate_conversion_funnel(db, "conversion_funnel.png")
    generate_discovery_engine(db, "discovery_channels.png")
    generate_feature_heatmap(db, "feature_intent.png")
    generate_release_correlation(db, "release_correlation.png")