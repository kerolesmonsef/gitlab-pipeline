# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Python CLI toolkit for automating GitLab pipeline and MR lifecycle at `https://git.foo.mobi`. No tests, no build step — scripts run directly with Python 3.8+.

## Setup

```bash
pip install rich python-dotenv
cp .env.example .env   # add GITLAB_TOKEN=glpat-...
```

## Running Scripts

```bash
# Trigger a pipeline
python trigger_pipeline.py --project-path "group/project" --branch "staging" --deploy "true"

# Push current branch + create MR + auto-track it
python create_merge_request.py --target staging

# Track an existing MR by URL
python mr_track.py --url "https://git.foo.mobi/group/project/-/merge_requests/123"

# Check pipeline status
python pipeline_status.py --latest
python pipeline_status.py --list
python pipeline_status.py --url "https://git.foo.mobi/group/project/-/pipelines/123"
python pipeline_status.py --latest --manual-deploy   # force-trigger manual deploy jobs

# Cancel a pipeline
python cancel_pipeline.py --url "https://git.foo.mobi/group/project/-/pipelines/123"

# Cron daemon (run every minute via crontab)
python cron.py                 # processes both MR and pipeline records
python cron.py --mode mr       # MR records only
python cron.py --mode pipeline # pipeline records only
```

Crontab entry: `* * * * * cd /path/to/project && python cron.py >> cron.log 2>&1`

## Architecture

Two storage modules act as the persistence layer — everything else reads/writes through them:

- **`Pipeline.py`** — CRUD for `pipeline.json` (list of active pipelines to watch)
- **`MR.py`** — CRUD for `mr.json` (list of open MRs to watch)

Both files are flat JSON arrays. The `attempts` counter in each record is the TTL mechanism — pipeline records expire at 30 attempts, MR records at 120.

**`pipeline_status.py`** is the shared API layer, not just a CLI. It exports `fetch_pipeline`, `fetch_jobs`, `get_pending_deploy_jobs`, `trigger_manual_jobs`, `api_get`, `api_post`, `parse_url`, and `STATUS_ICONS`. `cron.py` imports these directly.

**`cron.py`** is the automation core. Each run it:
1. Polls `mr.json` — when an MR merges, finds the post-merge pipeline SHA and promotes it into `pipeline.json`, then removes the MR record
2. Polls `pipeline.json` — finds any manual `deploy` jobs (by name substring match) and triggers them via the GitLab play API, then removes the pipeline record

**`create_merge_request.py`** wraps `git push origin branch -o merge_request.create -o merge_request.target=TARGET`, parses the MR URL from git output, fetches MR details from the API, and saves to `mr.json`.

## Key Conventions

- All scripts use `load_dotenv()` to read `GITLAB_TOKEN` from `.env`
- GitLab base URL is hardcoded as `https://git.foo.mobi` in each script (not centralized)
- Project paths are URL-encoded with `urllib.parse.quote(path, safe="")` before API calls
- "Deploy" jobs are identified by `"deploy" in job_name.lower()` — name-based, not stage-based
- All output uses `rich` with consistent panel/table styling; no logging framework
- `pipeline.json` and `mr.json` are runtime state files (gitignored); `cron.log` is the cron output log
