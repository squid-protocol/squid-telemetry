import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# The parsed release history (Highest version tag per day)
releases = {
    '2026-03-22': 'v1.0.2',
    '2026-03-23': 'v1.0.6',
    '2026-03-25': 'v1.1.2',
    '2026-03-28': 'v1.1.5',
    '2026-04-04': 'v1.1.6',
    '2026-04-19': 'v2.0.0',
    '2026-04-20': 'v2.0.2',
    '2026-04-22': 'v2.0.3',
    '2026-04-24': 'v2.0.5',
    '2026-04-25': 'v2.0.7',
    '2026-04-27': 'v2.0.8',
    '2026-04-28': 'v2.0.9',
    '2026-05-11': 'v2.1.0',
    '2026-05-12': 'v2.2.0',
    '2026-05-29': 'v2.2.1',
    '2026-05-31': 'v2.2.6',
    '2026-07-05': 'v2.3.0',
    '2026-07-10': 'v2.3.9',
    '2026-07-12': 'v2.3.12',
    '2026-07-13': 'v2.3.17'
}

def generate_release_correlation(db_path="traffic_metrics.db", output_path="release_correlation.png"):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    
    # Query the aggregated daily fetches across all sources
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

    if df.empty:
        print("No traffic data found in the database.")
        return

    # Convert strings to datetime objects for plotting
    df['date_dt'] = pd.to_datetime(df['date'])
    
    # Calculate the cumulative sum of the daily downloads
    df['cumulative_downloads'] = df['daily_downloads'].cumsum()
    
    # Set up the figure with a wide aspect ratio to accommodate the timeline
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Plot cumulative volume as a thick line chart
    ax.plot(df['date_dt'], df['cumulative_downloads'], color='#4682B4', linewidth=3, label='Cumulative Unique Fetches')

    # Iterate through the dictionary and drop a vertical line for every release date
    for date_str, version in releases.items():
        dt = pd.to_datetime(date_str)
        # Ensure the release happened within our collected telemetry window
        if not df.empty and dt >= df['date_dt'].min() and dt <= df['date_dt'].max():
            ax.axvline(x=dt, color='#ff7f0e', linestyle='--', linewidth=1.5, alpha=0.8)
            
            # Anchor the text label near the top of the graph, rotated for readability
            ax.text(dt, ax.get_ylim()[1] * 0.95, version, rotation=90, color='#d62728', 
                    fontweight='bold', fontsize=9, va='top', ha='right',
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8))

    # Formatting the chart
    ax.set_title("GitGalaxy Cumulative Downloads vs. Release Cadence", fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12, labelpad=10)
    ax.set_ylabel("Total Cumulative Fetches", fontsize=12, labelpad=10)
    
    # Format X-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    
    # Clean up bounding box and add grid
    ax.legend(loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle=':', alpha=0.4)
    
    plt.tight_layout()
    plt.savefig(output_path, format='png', dpi=150)
    print(f"Graph successfully rendered to: {output_path}")

if __name__ == "__main__":
    generate_release_correlation()