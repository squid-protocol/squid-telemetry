#!/usr/bin/env python3
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

def generate_cumulative_graph(db_path: str, output_path: str):
    # 1. Connect to the database and extract the daily totals
    conn = sqlite3.connect(db_path)
    
    query = """
        WITH combined_traffic AS (
            -- PyPI: Already filtered for 'without_mirrors' by scraper.py
            SELECT repo_name, date, downloads as volume 
            FROM pypi_downloads 
            
            UNION ALL
            
            -- GitHub: Using unique_cloners for a more stringent metric
            SELECT repo_name, date, unique_cloners as volume 
            FROM traffic_clones 
            
            UNION ALL
            
            -- GitLab: Extracting daily positive deltas from the rolling 30-day window
            SELECT repo_name, date, 
                   MAX(0, usage_count_30_days - COALESCE(LAG(usage_count_30_days) OVER (PARTITION BY repo_name ORDER BY date), 0)) as volume 
            FROM gitlab_catalog_usage 
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
    
    # Pivot the data so each repository has its own column of daily totals
    pivot_df = df.pivot(index='date', columns='repo_name', values='daily_downloads').fillna(0)
    
    # Calculate cumulative sum for all repositories simultaneously
    cumulative_df = pivot_df.cumsum()

    # 3. Render the Professional Graph
    import matplotlib.dates as mdates
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot target first for top legend ordering, use zorder=10 to guarantee visual priority
    if 'squid-protocol/gitgalaxy' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['squid-protocol/gitgalaxy'], 
                color='red', linewidth=3, label='gitgalaxy', zorder=10)
                
    # Plot language-crucible in green
    if 'squid-protocol/language-crucible' in cumulative_df.columns:
        ax.plot(cumulative_df.index, cumulative_df['squid-protocol/language-crucible'], 
                color='green', linewidth=2.5, label='language-crucible', zorder=9)
    
    # Plot the remaining negative controls in light gray as a grouped background layer
    added_baseline = False
    for repo in cumulative_df.columns:
        if repo not in ['squid-protocol/gitgalaxy', 'squid-protocol/language-crucible']:
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

if __name__ == "__main__":
    generate_cumulative_graph("traffic_metrics.db", "cumulative_downloads.png")