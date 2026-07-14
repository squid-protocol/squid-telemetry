# 🌌 GitGalaxy Telemetry & Analytics

**Primary Links:**
* ⚙️ **Main Engine Repository:** [squid-protocol/gitgalaxy](https://github.com/squid-protocol/gitgalaxy)
* 🗺️ **Live WebGL Architecture Map:** [squid-protocol.github.io/gitgalaxy/](https://squid-protocol.github.io/gitgalaxy/)

---

## Overview

This repository serves as the centralized, automated data warehouse and visualization pipeline for **GitGalaxy**. Because the core GitGalaxy engine operates as a zero-trust, air-gapped static analyzer, it does not "phone home" or collect telemetry on the machines running it. 

Instead, this repository passively aggregates our public distribution metrics—tracking how often the engine is fetched across GitHub, GitLab, and PyPI.

## 📈 Core Telemetry & Metrics

### Cumulative Adoption
Tracking the total, deduplicated volume of fetches across PyPI, GitHub, and GitLab against our baseline control repositories.
![GitGalaxy Cumulative Downloads](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/cumulative_downloads.png)

### The Conversion Funnel (14-Day Rolling)
Measuring the transition from passive human intent (unique repository profile views) to active pipeline execution (unique automated fetches).
![Conversion Funnel](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/conversion_funnel.png)

### Discovery Channels (14-Day Rolling)
Identifying the top referring external domains driving initial human discovery of the GitGalaxy architecture.
![Discovery Channels](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/discovery_channels.png)

### Feature Intent Heatmap (14-Day Rolling)
Mapping the most frequently inspected sub-directories and tools to understand what features users are auditing before pulling the engine.
![Feature Intent](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/feature_intent.png)

### Release Cadence vs. Downloads
Correlating daily download spikes directly against version releases to monitor CI/CD Dependabot automated updates and community launch responses.
![Release Correlation](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/release_correlation.png)

> *Graphs are generated automatically via Python/Matplotlib and synchronized daily via GitHub Actions.*

---

## How This Pipeline Works

This repository is completely self-contained and runs on an automated daily CRON schedule via GitHub Actions.

1. **The Scraper (`scraper.py`):** At UTC Midnight, the pipeline reaches out to the GitHub REST API, GitLab GraphQL API, and PyPI Stats API to pull the sliding 14-day window of clones, views, and downloads.
2. **The Database (`traffic_metrics.db`):** The raw JSON responses are normalized and safely upserted into a highly relational SQLite database.
3. **The Visualizers (`generate_graph.py` & `release_correlation.py`):** Pandas and Matplotlib scripts query the SQLite database to calculate rolling windows and cumulative totals, rendering the time-series data into clean, professional PNG artifacts.
4. **The Commit (`telemetry_pipeline.yml`):** The CI/CD runner automatically commits the updated database and new image artifacts back to this repository, ensuring the dashboard remains perfectly synchronized without manual intervention.