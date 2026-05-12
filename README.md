# GitLab Pipeline Automation

> Trigger pipelines, monitor deployments, and let the robots handle the rest.

---

## The Problem

Every time you want to deploy to staging, you find yourself:
- Opening GitLab manually
- Finding the right project and branch
- Clicking through the UI to trigger a pipeline
- Waiting for it to finish, then manually clicking "Play" on deploy jobs
- Doing this repeatedly throughout the day

It's not hard — it's just tedious. And tedious things are exactly what computers are good at solving.

---

## The Solution

This tool automates the entire pipeline lifecycle:

1. **Trigger pipelines** with a single command — no more clicking through GitLab UI
2. **Automate manual deploys** — the bot watches your pipelines and clicks "Play" when needed
3. **Track everything** — all pipeline records are saved locally so you know what's running

You run one command to start a pipeline. The bot handles the rest.

---

## Project Overview

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   trigger_pipeline.py    ──►    Start a new pipeline       │
│                                 with custom options         │
│                                                             │
│   cron.py               ──►    Watch and auto-trigger       │
│                                 manual deploy jobs           │
│                                                             │
│   pipeline_status.py    ──►    Check pipeline status         │
│                                 or trigger jobs manually     │
│                                                             │
│   Pipeline.py           ──►    Manage pipeline records      │
│                                 (storage layer)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Set Your GitLab Token

Create a `.env` file in the project root:

```bash
GITLAB_TOKEN=glpat-your-token-here
```

Find your token in GitLab: **Settings → Access Tokens** (needs `api` scope).

### 2. Trigger a Pipeline

```bash
python trigger_pipeline.py \
    --project-path "your-group/your-project" \
    --branch "staging" \
    --deploy "true"
```

This starts a pipeline and saves it to the tracking system. You'll see the pipeline URL in the output.

### 3. Let the Bot Work

Run the cron job — it checks all tracked pipelines every minute:

```bash
python cron.py
```

When a manual deploy job appears, the bot triggers it automatically. When the pipeline finishes, the record is cleaned up.

---

## What Each Tool Does

### 🔥 trigger_pipeline.py

**What it does:** Starts a new pipeline on a specific branch with custom settings.

**When to use it:** When you need to deploy or test something. Just run the command and the pipeline starts.

**Example:**
```bash
python trigger_pipeline.py \
    --project-path "adc/backends/backend-service" \
    --branch "staging" \
    --deploy "true" \
    --sonar-tests "true"
```

This triggers a staging deployment with SonarQube analysis enabled.

---

### ⏰ cron.py

**What it does:** Automatically triggers manual deploy jobs so you don't have to watch pipelines.

**When to use it:** Run this continuously (e.g., every minute via crontab). It watches your pipelines and acts when needed.

**How it works:**
1. Looks at all tracked pipelines
2. Checks if any have manual deploy jobs waiting
3. Triggers those jobs automatically
4. Removes finished pipelines from tracking
5. Gives up after 30 checks to prevent endless loops

**Setup:**
```bash
# Add to crontab (runs every minute)
* * * * * cd /path/to/project && python cron.py >> cron.log 2>&1
```

---

### 📊 pipeline_status.py

**What it does:** Shows pipeline status and lets you trigger manual jobs on demand.

**When to use it:** When you want to check what's happening without opening GitLab.

**Examples:**
```bash
# Check latest pipeline
python pipeline_status.py --latest

# Check specific pipeline
python pipeline_status.py --project "group/project" --pipeline-id 12345

# List all tracked pipelines
python pipeline_status.py --list

# Trigger manual deploys manually
python pipeline_status.py --latest --manual-deploy
```

---

## Pipeline Options

When triggering a pipeline, you can control what happens:

| Option | Purpose | Default |
|--------|---------|---------|
| `--deploy` | Run the deployment job | `true` |
| `--postman-tests` | Run API integration tests | `false` |
| `--sonar-tests` | Run code quality analysis | `false` |
| `--jmeter-load-test` | Run performance tests | `false` |
| `--jmeter-internal` | Run internal load tests | `false` |
| `--jmeter-external` | Run external load tests | `false` |
| `--docker-cache` | Use Docker layer caching | `false` |

---

## How It Tracks Pipelines

Every triggered pipeline is saved to `pipeline.json`. This file acts as a to-do list for the cron job.

```json
[
  {
    "pipeline_id": "12345",
    "project_path": "group/backend-service",
    "branch": "staging",
    "web_url": "https://gitlab.com/...",
    "variables": {"deploy": "true"},
    "triggered_at": "2026-05-12T10:30:00+00:00",
    "attempts": 3
  }
]
```

The `attempts` counter tracks how many times the cron job checked this pipeline. After 30 checks, it's automatically removed (to prevent clutter from stuck pipelines).

---

## Common Workflows

### Deploy to Staging

```bash
python trigger_pipeline.py \
    --project-path "group/my-service" \
    --branch "staging" \
    --deploy "true"
```

Then let `cron.py` handle any manual deploy jobs.

### Deploy with Testing

```bash
python trigger_pipeline.py \
    --project-path "group/my-service" \
    --branch "staging" \
    --deploy "true" \
    --sonar-tests "true" \
    --postman-tests "true"
```

### Check Status Later

```bash
# See all tracked pipelines
python pipeline_status.py --list

# Check specific one
python pipeline_status.py --latest
```

### Manual Intervention

```bash
# Force trigger manual deploys
python pipeline_status.py --latest --manual-deploy
```

---

## Setup Requirements

- **Python 3.8+**
- **GitLab token** with API access
- **Rich library** for nice terminal output: `pip install rich`

---

## Troubleshooting

**Pipeline not triggering?**
- Check your `GITLAB_TOKEN` is set correctly
- Verify the project path exists in GitLab

**Cron job not running?**
```bash
# Check crontab
crontab -l

# View logs
tail -f cron.log
```

**Manual deploy jobs not auto-triggering?**
- Run `pipeline_status.py --latest` to see job details
- Use `--manual-deploy` flag to trigger them manually

---

## Why This Exists

CI/CD pipelines are great, but GitLab's manual jobs require someone to babysit them. This tool removes that requirement — you trigger a pipeline, and the system handles everything else until completion.

It's essentially a robot that watches your pipelines and clicks "Play" when needed, so you can focus on writing code instead of clicking buttons.