#!/usr/bin/env python3
"""Cron job: poll pipeline.json, auto-trigger manual deploys, remove finished records.

Usage:
    GITLAB_TOKEN=glpat-xxxx python cron.py

Run this on a schedule (e.g. every minute via crontab) to keep pipeline.json
up-to-date without manual intervention:

    * * * * * cd /path/to/project && GITLAB_TOKEN=glpat-xxxx python cron.py >> cron.log 2>&1
"""

import os
import sys
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import Pipeline
import pipeline_status as ps

console = Console()

MAX_ATTEMPTS = 30


def run() -> None:
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        console.print(
            Panel.fit(
                "[bold red]✘ GITLAB_TOKEN is not set.[/bold red]",
                title="[bold magenta]⚠️ Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)

    records = Pipeline.read_all()
    if not records:
        console.print(
            Panel.fit(
                "[dim](no pipeline records in pipeline.json — nothing to do)[/dim]",
                title="[bold magenta]ℹ️  Info[/bold magenta]",
                border_style="cyan",
                box=box.DOUBLE_EDGE,
            )
        )
        return

    console.print(
        Panel.fit(
            f"[bold cyan]Processing[/bold cyan] [yellow]{len(records)}[/yellow] [dim]record(s)...[/dim]\n"
            f"[dim]Time:[/dim] [green]{datetime.now(timezone.utc).isoformat()}[/green]",
            title="[bold magenta]⏰ Cron Job Started[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    for record in list(records):
        pipeline_id = record["pipeline_id"]
        project = record["project_path"]
        encoded_project = urllib.parse.quote(project, safe="")

        console.print(
            f"\n[bold]─── Pipeline #{pipeline_id} ({project}) ───[/bold]"
        )

        try:
            # ── 1. Fetch current status from GitLab ──────────────────────────────
            pipeline = ps.fetch_pipeline(encoded_project, pipeline_id, token)
            status = pipeline.get("status", "unknown")
            icon = ps.STATUS_ICONS.get(status, "❓")
            console.print(
                f"  [dim]Status:[/dim] {icon} [yellow]{status}[/yellow]"
            )

            # ── 2. Increment attempts; delete if MAX_ATTEMPTS reached ─────────────
            attempts = Pipeline.increment_attempts(pipeline_id)
            if attempts is None:
                continue
            console.print(f"  [dim]Attempts:[/dim] [cyan]{attempts}/{MAX_ATTEMPTS}[/cyan]")
            if attempts >= MAX_ATTEMPTS:
                console.print(
                    Panel.fit(
                        f"[bold red]✘ Pipeline #{pipeline_id} reached MAX_ATTEMPTS ({MAX_ATTEMPTS})[/bold red]\n"
                        f"[dim]Removing from pipeline.json...",
                        title="[bold magenta]⚠️ Max Attempts Reached[/bold magenta]",
                        border_style="red",
                        box=box.DOUBLE_EDGE,
                    )
                )
                Pipeline.delete(pipeline_id)
                continue

            # ── 3. Check for manual deploy jobs ──────────────────────────────────
            jobs = ps.fetch_jobs(encoded_project, pipeline_id, token)
            pending = ps.get_pending_deploy_jobs(jobs)

            if pending:
                console.print(
                    Panel.fit(
                        f"[bold cyan]{len(pending)}[/bold cyan] [dim]manual deploy job(s) found[/dim]",
                        title="[bold magenta]🖐️ Manual Deploy Jobs[/bold magenta]",
                        border_style="yellow",
                        box=box.DOUBLE_EDGE,
                    )
                )
                ps.trigger_manual_jobs(encoded_project, pending, token)
                console.print(
                    f"[bold green]✓[/bold green] [dim]Triggered and removed record[/dim]"
                )
                Pipeline.delete(pipeline_id)
            else:
                console.print(
                    f"  [dim]No manual deploy jobs pending[/dim] [yellow](status: {status})[/yellow]"
                )
        except Exception as e:
            console.print(
                Panel.fit(
                    f"[bold red]✘ {e}[/bold red]",
                    title="[bold magenta]❌ Failed to Fetch Pipeline[/bold magenta]",
                    border_style="red",
                    box=box.DOUBLE_EDGE,
                )
            )
            continue


if __name__ == "__main__":
    run()