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

    # 3. Render the XKCD-Style Graph
    with plt.xkcd():
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot the negative controls first so they sit in the background
        for repo in cumulative_df.columns:
            if repo != 'squid-protocol/gitgalaxy':
                # Strip the username from the label for a cleaner legend
                clean_name = repo.split('/')[-1]
                ax.plot(cumulative_df.index, cumulative_df[repo], color='gray', alpha=0.4, linewidth=1.5, label=clean_name)
        
        # Plot the primary target last so it renders on top
        if 'squid-protocol/gitgalaxy' in cumulative_df.columns:
            ax.plot(cumulative_df.index, cumulative_df['squid-protocol/gitgalaxy'], color='#8A2BE2', linewidth=3, label='gitgalaxy (Target)')
        
        # Formatting the chart
        ax.set_title("GitGalaxy vs. Baseline Repositories (Cumulative)", fontsize=18, pad=20)
        ax.set_xlabel("Date", fontsize=14, labelpad=10)
        ax.set_ylabel("Total Unique Fetches", fontsize=14, labelpad=10)
        
        # Add a legend to explicitly map the controls
        ax.legend(loc='upper left', fontsize=10)
        
        # Remove the top and right spines for a cleaner look
        ax.spines['top'].set_color('none')
        ax.spines['right'].set_color('none')
        
        plt.xticks(rotation=45)
        ax.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        
        # 4. Save the artifact
        plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
        print(f"Graph successfully rendered to: {output_path}")

if __name__ == "__main__":
    generate_cumulative_graph("traffic_metrics.db", "cumulative_downloads.png")