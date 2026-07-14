# 🌌 GitGalaxy Telemetry & Analytics

**Primary Links:**
* ⚙️ **Main Engine Repository:** [squid-protocol/gitgalaxy](https://github.com/squid-protocol/gitgalaxy)
* 🗺️ **Live WebGL Architecture Map:** [squid-protocol.github.io/gitgalaxy/](https://squid-protocol.github.io/gitgalaxy/)

---

## Overview

This repository serves as the centralized, automated data warehouse and visualization pipeline for **GitGalaxy**. Because the core GitGalaxy engine operates as a zero-trust, air-gapped static analyzer, it does not "phone home" or collect telemetry on the machines running it. 

Instead, this repository passively aggregates our public distribution metrics—tracking how often the engine is fetched across GitHub, GitLab, and PyPI.

## Cumulative Adoption

![GitGalaxy Cumulative Downloads](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/cumulative_downloads.png)

> *Graph automatically generated and updated daily via GitHub Actions.*

---

## How This Pipeline Works

This repository is completely self-contained and runs on an automated daily CRON schedule via GitHub Actions.

1. **The Scraper (`scraper.py`):** At UTC Midnight, the pipeline reaches out to the GitHub REST API, GitLab GraphQL API, and PyPI Stats API to pull the sliding 14-day window of clones, views, and downloads.
2. **The Database (`traffic_metrics.db`):** The raw JSON responses are normalized and safely upserted into a highly relational SQLite database.
3. **The Visualizer (`generate_graph.py`):** A Pandas and Matplotlib script queries the SQLite database to calculate the cumulative totals, rendering the time-series data into the `matplotlib.xkcd()` stylized PNG displayed above.
4. **The Commit (`scrape_and_graph.yml`):** The CI/CD runner automatically commits the updated database and new image artifact back to this repository, ensuring the dashboard remains perfectly synchronized without manual intervention.