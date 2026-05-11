# GitLab Pipeline Automation

A Python-based automation tool for managing GitLab CI/CD pipelines. This project provides:

- **Manual pipeline triggering** via `trigger_pipeline.py`
- **Automatic monitoring** via `cron.py` to handle manual deploy jobs

## Prerequisites

- Python 3.8+
- GitLab private token with API access
- Required packages:
  ```bash
  pip install rich
  ```

## Project Structure

| File | Description |
|------|-------------|
| `trigger_pipeline.py` | Manually trigger GitLab pipelines with configurable variables |
| `cron.py` | Cron job that polls pipelines and auto-triggers manual deploy jobs |
| `Pipeline.py` | Module for managing pipeline records in `pipeline.json` |
| `pipeline.json` | JSON file storing pipeline records |
| `pipeline_status.py` | GitLab API status checking module |

---

## Step 1: Set GitLab Token

Create a `.env` file or export the token directly:

```bash
# Option 1: Export variable (temporary)
export GITLAB_TOKEN="glpat-xxxx"

# Option 2: Add to ~/.bashrc or ~/.zshrc (permanent)
echo 'export GITLAB_TOKEN="glpat-xxxx"' >> ~/.bashrc
source ~/.bashrc
```

Replace `glpat-xxxx` with your actual GitLab private token.

---

## Step 2: Trigger a Pipeline (First)

To trigger a pipeline, run:

```bash
GITLAB_TOKEN="glpat-xxxx" python trigger_pipeline.py \
    --project-path "adc/backends/project-name" \
    --branch "staging" \
    --deploy "true"
```

### Available Options

| Flag | Description | Default |
|------|-------------|----------|
| `--project-path` | GitLab project path | `adc/backends/project-name` |
| `--branch` | Branch to trigger | `staging` |
| `--deploy` | Enable deploy job | `true` |
| `--postman-tests` | Run Postman tests | `false` |
| `--sonar-tests` | Run SonarQube tests | `false` |
| `--jmeter-load-test` | Run JMeter load test | `false` |
| `--docker-cache` | Enable Docker cache | `false` |

This will create a pipeline and save the record to `pipeline.json`.

---

## Step 3: Run Cron Job Manually (Test)

Before adding to crontab, test the cron script manually:

```bash
GITLAB_TOKEN="glpat-xxxx" python cron.py
```

Expected output:
- Shows processing status of all pipelines in `pipeline.json`
- Checks each pipeline status from GitLab API
- Auto-triggers any pending manual deploy jobs
- Removes finished records after completion

---

## Step 4: Add to Crontab (Every 1 Minute)

### 4.1: Open crontab editor

```bash
crontab -e
```

### 4.2: Add this line

```cron
* * * * * cd /path/to/project && GITLAB_TOKEN=glpat-xxxx python cron.py >> cron.log 2>&1
```

Replace `/path/to/project` with the actual absolute path to this project.

### 4.3: Save and exit

Press `Esc`, then type `:wq` to save and exit (if using vim/nano).

---

## Understanding the Output Redirection

The `>> cron.log 2>&1` redirect means:

| Part | Description |
|------|-------------|
| `>>` | Append output to file (preserve previous logs) |
| `cron.log` | Log file name |
| `2>&1` | Redirect stderr (error) to stdout, so both go to the log file |

This saves all output (including errors) to `cron.log`.

### View the logs

```bash
# View latest entries
tail -f cron.log

# View entire log
cat cron.log
```

---

## How It Works

1. **Trigger**: `trigger_pipeline.py` creates a pipeline via GitLab API and saves record to `pipeline.json`

2. **Cron Job** (`cron.py` runs every minute):
   - Reads pipeline records from `pipeline.json`
   - Checks each pipeline status from GitLab API
   - Increments attempt counter (max 60 attempts)
   - If manual deploy jobs are pending → triggers them and removes record
   - If max attempts reached → removes record automatically

3. **Cleanup**: Records are removed when:
   - Manual deploy jobs are successfully triggered
   - Pipeline completes (success/failed/canceled)
   - Max attempts (60) reached

---

## Troubleshooting

### View crontab entries

```bash
crontab -l
```

### Remove crontab

```bash
crontab -r
```

### Check cron service status

```bash
# Linux (systemd)
systemctl status cron

# macOS
launchctl list | grep cron
```

### Manual log check

```bash
cat cron.log
```

---

## Pipeline.json Format

```json
[
  {
    "pipeline_id": "250704",
    "project_path": "adc/backends/adc-minting-backend",
    "branch": "staging",
    "web_url": "https://git.foo.mobi/...",
    "variables": {...},
    "triggered_at": "2026-05-11T00:14:44.818757+00:00",
    "attempts": 10
  }
]
```

---

## Additional Commands

### List all pipeline records

```bash
python -c "import Pipeline; Pipeline.list_all(verbose=True)"
```

### Delete a specific pipeline record

```bash
python -c "import Pipeline; Pipeline.delete('250704')"
```

### Clear all records

```python
python -c "import Pipeline; [Pipeline.delete(r['pipeline_id']) for r in list(Pipeline.read_all())]"
```

---

## References

- GitLab API: `https://docs.gitlab.com/16ee/api/index.html`
- Rich library: `https://rich.readthedocs.io/`