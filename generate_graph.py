#!/usr/bin/env python3
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

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

if __name__ == "__main__":
    generate_cumulative_graph("traffic_metrics.db", "cumulative_downloads.png")