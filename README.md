# 🌌 GitGalaxy Telemetry & Analytics

**Primary Links:**
* ⚙️ **Main Engine Repository:** [squid-protocol/gitgalaxy](https://github.com/squid-protocol/gitgalaxy)
* 🗺️ **Live WebGL Architecture Map:** [squid-protocol.github.io/gitgalaxy/](https://squid-protocol.github.io/gitgalaxy/)

---

## Overview

This repository is the automated data warehouse and chart pipeline for **GitGalaxy**'s public distribution metrics. The engine is a zero-trust, air-gapped static analyzer and phones nothing home, so everything here comes from what GitHub, GitLab and PyPI publish about the repos: clones, views, referrers, stars, forks and downloads.

## How to read these numbers

**Most of the raw clone volume is us.** GitGalaxy is built and proven by an autonomous coding fleet whose CI checks out the engine and its crucibles thousands of times a day. GitHub's clone counter can't tell those fetches from anyone else's, so raw clone curves mostly measure our own activity, not adoption. As of 2026-10-17:

- gitgalaxy: ~93% of the last 28 days' clones were repeat clones by the same cloner (largely our CI); an estimated ~45 *possibly-outside* unique cloners a day remain, an upper estimate since it still holds our own local and fleet machines.
- The crucibles and keyword-rosetta are almost entirely our CI. language-crucible's leftover (~16/day) still moves with our own CI.
- Signals that track people more directly: 57 stars, 12 forks, ~10 unique visitors a day, Reddit as the main referrer, ~15k PyPI downloads (raw, CI installs included) that peaked in July. No repo outside squid-protocol uses the GitHub Action yet, and GitLab Catalog usage is 0.

So: the **Total Engagement** chart is raw activity, ours included. Read adoption from the estimate charts and the human signals below, never from raw clone volume.

## 📈 Charts

### Total Engagement (raw, includes our own CI and fleet)
Every fetch we can see, nothing subtracted: GitHub clones plus PyPI downloads plus GitLab Catalog usage for the engine, and GitHub clones for the rest of the ecosystem, i.e. the crucibles (`language-crucible`, `cics-crucible`, `estate-crucible`, `temporal-crucible`, `keyword-rosetta`), the AI harness (`squid-bot`, `promoter-bot`) and the evidence & example repos (`gitgalaxy-raw-output`, `gitgalaxy-population-analyses`, `cobol_to_java_examples`). Linear axis; each line starts on its first tracked day and is labeled with its running total. These are clone/download **events**, not people, and most of them are ours: this chart shows total activity, not adoption.
![Total Engagement](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/cumulative_downloads.png)

### Cumulative Clones, Our Own Traffic Removed (estimate)
The same view, counting only each repo's *possibly-outside* unique cloners (the split below). Each line starts on the first day an own-CI estimate exists for that repo. **"(floor)"** marks repos where our CI accounts for the unique cloners on most days, so outside traffic there is hidden, not absent. PyPI can't be split (no per-machine data) and is left off; its raw total is in the footnote. "Possibly outside" is an upper estimate: our own fetches the estimate can't see (local clones, fleet machines) land in it too.
![Cumulative clones, our traffic removed](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/cumulative_outside.png)

### Where the Clones Come From (estimate)
Each repo's GitHub clones split per day into **repeat clones** (`total - unique`: the same cloner again that day; people rarely do it, our CI, fleet and agent worktrees constantly do), **our CI** (the unique cloners our own workflows account for, see Methodology) and **possibly outside** (what's left). Top: each repo's share over the last 28 days. Below: daily bars for the six busiest repos. A rough split, not an audit.
![Where the clones come from](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/clone_sources.png)

### Discovery & Usage
Left: GitHub stars and forks (cumulative, rebuilt from each star's and fork's own timestamp). Middle: unique cloners per day, all (faint, mostly our CI) and possibly outside (bold, estimate), plus unique visitors per day; these are per-day counts, never cumulated. Right: CI integration by **outside** repos only: GitLab CI/CD Catalog usage (unique projects, last 30 days) and repos outside squid-protocol whose workflows reference `squid-protocol/gitgalaxy` (code search). Both are 0 so far: the only workflow match has always been our own gitgalaxy repo.
![Discovery & Usage](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/human_vs_ci_adoption.png)

### Discovery Channels (ranked all-time, plotted as trailing 14 days)
The top referring domains. GitHub reports referrers only as a trailing-14-day total, so each point is one day's 14-day window. Rankings and legend totals come from **non-overlapping** 14-day snapshots only (see Methodology) and are *visitor-windows*, not people. Our own browsing is included (it can't be separated).
![Discovery Channels](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/discovery_channels.png)

### Feature Intent Heatmap (ranked all-time, plotted as trailing 14 days)
The most-viewed sub-directories and tools, with the same trailing-14-day series and non-overlapping-window ranking as Discovery Channels; totals are visitor-windows and include our own browsing.
![Feature Intent](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/feature_intent.png)

### Releases vs. Outside-Facing Downloads
PyPI downloads (raw: includes CI installs, so a release also triggers bots and pipelines) and gitgalaxy's possibly-outside GitHub cloners, both cumulative, against PyPI release dates. Combined raw clone volume is deliberately not used: its "release spikes" were our own pipelines reacting to our own releases.
![Release Correlation](https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/release_correlation.png)

> *Charts are generated with Python/Matplotlib and refreshed daily by GitHub Actions.*

---

## Methodology Notes

Not every "count" below means the same thing:

| Source | What we store | Deduplicated? |
|---|---|---|
| GitHub (`traffic/clones`, `traffic/views`) | `total_clones`, `unique_cloners`, `unique_visitors` | Uniques are per **day** only; summing days gives cloner-days / visitor-days, not people. GitHub folds token-authenticated fetches (our `actions/checkout` CI) into very few unique cloners, about 12 checkouts per unique cloner for gitgalaxy, while anonymous `git clone` runners each count as new. |
| GitLab CI/CD Catalog | `last30DayUsageCount` | Yes, unique *projects* (per GitLab's docs), not pipeline runs. |
| PyPI (`pypistats.org`, `without_mirrors`) | raw download count | **No.** PyPI's public data has no identity to deduplicate against; `without_mirrors` drops known mirror bots but **not** CI installs (Dependabot, Actions matrices, Docker builds). Distribution *volume*, not adopters. |
| GitHub Action adoption (code search) | repos matching `"squid-protocol/gitgalaxy"` under `.github/workflows`: `unique_repos` (all) and `external_repos` (outside squid-protocol, collected from 2026-10-18) | Deduped by repo; default branch only; can slightly over-count (matches a comment too). Charts use outside repos only. Before `external_repos` existed, `unique_repos` never exceeded 1 and that match was our own gitgalaxy repo. |
| GitHub referrers / popular paths (`referring_sites`, `popular_content`) | one row per fetch date, each a **trailing 14-day rolling total** | Within a window only. "All-time" figures sum only **non-overlapping** snapshots (`aggregation.py`, tested in `tests/`), giving *visitor-windows*: a person active in two windows counts twice. |
| Own-CI fetch estimate (`own_ci_checkouts`; engine-only history in `own_ci_clones`) | per day, workflow and target repo: Actions runs x fetches of that repo per run, counted from the workflow YAML (`actions/checkout` steps plus `git clone` / `git remote add` lines) across `OWN_CI_REPOS` | **Estimate.** Static count: matrix jobs, multi-job workflows and retries aren't multiplied; `if:`-skipped steps and cancelled runs still count. Local and fleet-machine fetches are not observable. Refill history with the workflow's `own_ci_backfill_days` input (30 days takes ~40 min). |
| Unique cloners per CI fetch (`ci_unique_rate`) | fitted per repo at chart time: slope of daily unique cloners on daily CI fetches, clipped to 0..2 | Needs 20+ days and 100+ CI fetches, else 1 is assumed. gitgalaxy fits ~0.08 (token-authenticated checkouts collapse); language-crucible ~1.27 (anonymous clones, plus fetches the static count misses). Our CI's share of a day's unique cloners = CI fetches x this rate, capped at the day's uniques. |

## How This Pipeline Works

This repository is completely self-contained and runs on an automated daily CRON schedule via GitHub Actions.

1. **The Scraper (`scraper.py`):** At UTC midnight, the pipeline calls the GitHub REST API (traffic, repo stats, code search, Actions runs for the own-CI estimate), GitLab GraphQL API and PyPI Stats API to pull the sliding 14-day window of clones/views, stars/forks, and downloads.
2. **The Database (`traffic_metrics.db`):** The raw JSON responses are normalized and safely upserted into a highly relational SQLite database.
3. **The Visualizer (`generate_graph.py`):** Pandas and Matplotlib query the SQLite database to calculate rolling windows and cumulative totals, rendering the PNG charts. (`release_correlation.py` at the repo root is an earlier, standalone iteration of this file's release-correlation chart, kept for reference — it isn't invoked by the pipeline.)
4. **The Commit (`telemetry_pipeline.yml`):** The CI/CD runner automatically commits the updated database and new image artifacts back to this repository, rebasing onto `main` first so a long run isn't lost when something merges meanwhile.
---

## The GitGalaxy constellation

This repo is one strand of the web of repos that build, prove, and showcase
[GitGalaxy](https://github.com/squid-protocol/gitgalaxy). This one tracks how the engine
**spreads** (fetches, views, referrers); the runtime evidence for what it *does* lives next door:

- [gitgalaxy](https://github.com/squid-protocol/gitgalaxy) — the engine these metrics track
- **squid-telemetry** — *you are here*: public distribution analytics, with our own traffic estimated and separated (the engine itself is air-gapped and phones nothing home)
- [gitgalaxy-raw-output](https://github.com/squid-protocol/gitgalaxy-raw-output) — unedited scan outputs + speed telemetry on hundreds of real repos
- [language-crucible](https://github.com/squid-protocol/language-crucible) — the pinned adversarial corpus behind the engine's golden-master regression gate
- [keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta) — one planted program in 46 languages, measuring cross-language measurement consistency
- [gitgalaxy-population-analyses](https://github.com/squid-protocol/gitgalaxy-population-analyses) — statistical analyses over the scan population
- [cobol_to_java_examples](https://github.com/squid-protocol/cobol_to_java_examples) — 10 COBOL repos auto-translated to compiling Spring Boot architectures
- Docs: [architecture & methodology site](https://squid-protocol.github.io/gitgalaxy/) · [Museum of Code](https://squid-protocol.github.io/gitgalaxy/museum-of-code/) · [gitgalaxy.io](https://gitgalaxy.io/) · [PyPI](https://pypi.org/project/gitgalaxy/) · [demo video](https://www.youtube.com/watch?v=XWWSd8LmoCM)
