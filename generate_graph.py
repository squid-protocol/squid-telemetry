#!/usr/bin/env python3
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

def generate_cumulative_graph(db_path: str, output_path: str):
    # 1. Connect to the database and extract the daily totals
    conn = sqlite3.connect(db_path)
    
    query = """
        WITH combined_traffic AS (
            SELECT date, downloads as volume 
            FROM pypi_downloads 
            WHERE repo_name = 'squid-protocol/gitgalaxy'
            UNION ALL
            SELECT date, total_clones as volume 
            FROM traffic_clones 
            WHERE repo_name = 'squid-protocol/gitgalaxy'
        )
        SELECT date, SUM(volume) as daily_downloads 
        FROM combined_traffic 
        GROUP BY date 
        ORDER BY date ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 2. Process the data
    if df.empty:
        print("No PyPI download data found in the database.")
        return

    df['date'] = pd.to_datetime(df['date'])
    # Calculate the cumulative sum of the daily downloads
    df['cumulative_downloads'] = df['daily_downloads'].cumsum()

    # 3. Render the XKCD-Style Graph
    # The plt.xkcd() context manager automatically applies the comic-book font and jitter
    with plt.xkcd():
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot the line with a slight thickness for the hand-drawn feel
        ax.plot(df['date'], df['cumulative_downloads'], color='#8A2BE2', linewidth=3)
        
        # Formatting the chart
        ax.set_title("GitGalaxy Cumulative Adoption (PyPI + GitHub)", fontsize=18, pad=20)
        ax.set_xlabel("Date", fontsize=14, labelpad=10)
        ax.set_ylabel("Clones & Downloads", fontsize=14, labelpad=10)
        
        # Remove the top and right spines for a cleaner look
        ax.spines['top'].set_color('none')
        ax.spines['right'].set_color('none')
        
        # Rotate dates for readability
        plt.xticks(rotation=45)
        
        # Add a grid to make the values easier to trace
        ax.grid(True, linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        
        # 4. Save the artifact
        plt.savefig(output_path, format='png', bbox_inches='tight', dpi=150)
        print(f"Graph successfully rendered to: {output_path}")

if __name__ == "__main__":
    generate_cumulative_graph("traffic_metrics.db", "cumulative_downloads.png")