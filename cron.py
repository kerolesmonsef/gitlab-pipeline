#!/usr/bin/env python3
"""Cron job: poll pipeline.json and mr.json, auto-trigger manual deploys, remove finished records.

Usage:
    GITLAB_TOKEN=glpat-xxxx python cron.py

Run this on a schedule (e.g. every minute via crontab) to keep records
up-to-date without manual intervention:

    * * * * * cd /path/to/project && GITLAB_TOKEN=glpat-xxxx python cron.py >> cron.log 2>&1
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich import box

import MR
import Pipeline
import pipeline_status as ps

console = Console()

MR_MAX_ATTEMPTS = 120
PIPELINE_MAX_ATTEMPTS = 30
GITLAB_URL = "https://git.foo.mobi"


def _api_get(path: str, token: str):
    req = urllib.request.Request(
        f"{GITLAB_URL}/api/v4{path}",
        headers={"PRIVATE-TOKEN": token},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")


def _api_post_soft(path: str, token: str, data: bytes = b""):
    """POST that returns None on HTTP error instead of raising."""
    req = urllib.request.Request(
        f"{GITLAB_URL}/api/v4{path}",
        data=data,
        headers={"PRIVATE-TOKEN": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError:
        return None


def process_mr_records(token: str) -> None:
    records = MR.read_all()
    if not records:
        return

    console.print(
        Panel.fit(
            f"[bold cyan]Processing[/bold cyan] [yellow]{len(records)}[/yellow] [dim]MR record(s)...[/dim]",
            title="[bold magenta]🔀 MR Tracker[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    for record in list(records):
        project = record["project_path"]
        mr_iid = record["mr_iid"]
        encoded_project = urllib.parse.quote(project, safe="")

        console.print(f"\n[bold]─── MR !{mr_iid} ({project}) ───[/bold]")

        try:
            mr = _api_get(f"/projects/{encoded_project}/merge_requests/{mr_iid}", token)
            state = mr.get("state", "unknown")

            STATE_ICONS = {"opened": "🟢", "merged": "🟣", "closed": "🔴"}
            icon = STATE_ICONS.get(state, "⚪")
            console.print(f"  [dim]State:[/dim] {icon} [yellow]{state}[/yellow]")

            if state == "closed":
                console.print(f"  [dim]MR closed — removing from mr.json[/dim]")
                MR.delete(project, mr_iid)
                continue

            if state == "merged":
                merge_commit_sha = mr.get("merge_commit_sha") or mr.get("squash_commit_sha")
                if not merge_commit_sha:
                    console.print(f"  [dim]Merged but no commit SHA yet — retrying next run[/dim]")
                    MR.increment_attempts(project, mr_iid)
                    continue

                console.print(f"  [dim]Merge SHA:[/dim] [cyan]{merge_commit_sha[:8]}[/cyan]")

                # Find the post-merge pipeline on the target branch
                pipelines = _api_get(
                    f"/projects/{encoded_project}/pipelines?sha={merge_commit_sha}",
                    token,
                )

                if not pipelines:
                    attempts = MR.increment_attempts(project, mr_iid)
                    console.print(
                        f"  [dim]No post-merge pipeline yet — attempt [cyan]{attempts}/{MR_MAX_ATTEMPTS}[/cyan][/dim]"
                    )
                    if attempts >= MR_MAX_ATTEMPTS:
                        console.print(f"  [bold red]✘ Max attempts reached — removing MR record[/bold red]")
                        MR.delete(project, mr_iid)
                    continue

                # Take the most recent pipeline for this SHA
                post_merge_pipeline = pipelines[0]
                pipeline_id = str(post_merge_pipeline["id"])
                pipeline_url = post_merge_pipeline.get("web_url", "")
                branch = post_merge_pipeline.get("ref", record.get("target_branch", ""))
                pipeline_status = post_merge_pipeline.get("status", "unknown")

                console.print(
                    Panel.fit(
                        f"[bold green]✓ Post-merge pipeline found[/bold green]\n"
                        f"[dim]Pipeline:[/dim] [cyan]#{pipeline_id}[/cyan]\n"
                        f"[dim]Branch:[/dim] [green]{branch}[/green]\n"
                        f"[dim]Status:[/dim] [yellow]{pipeline_status}[/yellow]",
                        title="[bold magenta]🚀 Promoting to Pipeline Tracker[/bold magenta]",
                        border_style="green",
                        box=box.DOUBLE_EDGE,
                    )
                )

                Pipeline.create(
                    pipeline_id=pipeline_id,
                    project_path=project,
                    branch=branch,
                    web_url=pipeline_url,
                    variables={"promoted_from_mr": str(mr_iid)},
                )
                MR.delete(project, mr_iid)
                console.print(f"  [bold green]✓[/bold green] [dim]MR removed, pipeline #{pipeline_id} now tracked[/dim]")
                continue

            # state == "opened" — try auto-merge if flagged, otherwise wait
            if record.get("auto_merge"):
                console.print(f"  [dim]auto_merge=true — attempting merge...[/dim]")
                merge_result = _api_post_soft(
                    f"/projects/{encoded_project}/merge_requests/{mr_iid}/merge",
                    token,
                )
                if merge_result is None:
                    console.print(f"  [dim]Not mergeable yet — will retry next cycle[/dim]")
                else:
                    console.print(f"  [bold green]✓[/bold green] [dim]Merge triggered — will pick up pipeline next cycle[/dim]")

            attempts = MR.increment_attempts(project, mr_iid)
            console.print(f"  [dim]Still open — attempt [cyan]{attempts}/{MR_MAX_ATTEMPTS}[/cyan][/dim]")
            if attempts >= MR_MAX_ATTEMPTS:
                console.print(f"  [bold red]✘ Max attempts reached — removing MR record[/bold red]")
                MR.delete(project, mr_iid)

        except Exception as e:
            console.print(
                Panel.fit(
                    f"[bold red]✘ {e}[/bold red]",
                    title="[bold magenta]❌ Failed to fetch MR[/bold magenta]",
                    border_style="red",
                    box=box.DOUBLE_EDGE,
                )
            )
            continue


def process_pipeline_records(token: str) -> None:
    records = Pipeline.read_all()
    if not records:
        return

    console.print(
        Panel.fit(
            f"[bold cyan]Processing[/bold cyan] [yellow]{len(records)}[/yellow] [dim]pipeline record(s)...[/dim]\n"
            f"[dim]Time:[/dim] [green]{datetime.now(timezone.utc).isoformat()}[/green]",
            title="[bold magenta]⏰ Pipeline Tracker[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    for record in list(records):
        pipeline_id = record["pipeline_id"]
        project = record["project_path"]
        encoded_project = urllib.parse.quote(project, safe="")

        console.print(f"\n[bold]─── Pipeline #{pipeline_id} ({project}) ───[/bold]")

        try:
            pipeline = ps.fetch_pipeline(encoded_project, pipeline_id, token)
            status = pipeline.get("status", "unknown")
            icon = ps.STATUS_ICONS.get(status, "❓")
            console.print(f"  [dim]Status:[/dim] {icon} [yellow]{status}[/yellow]")

            attempts = Pipeline.increment_attempts(pipeline_id)
            if attempts is None:
                continue
            console.print(f"  [dim]Attempts:[/dim] [cyan]{attempts}/{PIPELINE_MAX_ATTEMPTS}[/cyan]")
            if attempts >= PIPELINE_MAX_ATTEMPTS:
                console.print(
                    Panel.fit(
                        f"[bold red]✘ Pipeline #{pipeline_id} reached max attempts ({PIPELINE_MAX_ATTEMPTS})[/bold red]\n"
                        f"[dim]Removing from pipeline.json...",
                        title="[bold magenta]⚠️ Max Attempts Reached[/bold magenta]",
                        border_style="red",
                        box=box.DOUBLE_EDGE,
                    )
                )
                Pipeline.delete(pipeline_id)
                continue

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
                console.print(f"[bold green]✓[/bold green] [dim]Triggered and removed record[/dim]")
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


def run() -> None:
    parser = argparse.ArgumentParser(description="GitLab cron: poll MR and pipeline records")
    parser.add_argument(
        "--mode",
        choices=["mr", "pipeline", "all"],
        default="all",
        help="Which records to process (default: all)",
    )
    args = parser.parse_args()

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

    if args.mode in ("mr", "all"):
        process_mr_records(token)

    if args.mode in ("pipeline", "all"):
        process_pipeline_records(token)


if __name__ == "__main__":
    run()
