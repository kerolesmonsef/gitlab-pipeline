import argparse
import json
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()
import urllib.error
import urllib.parse
import urllib.request

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import Pipeline

console = Console()

GITLAB_URL = "https://git.foo.mobi"

STATUS_ICONS = {
    "success": "✅",
    "failed": "❌",
    "running": "🔄",
    "pending": "⏳",
    "canceled": "🚫",
    "skipped": "⏭️",
    "manual": "🖐️",
    "scheduled": "📅",
    "created": "🆕",
    "waiting_for_resource": "⏳",
    "preparing": "⚙️",
}


def api_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{GITLAB_URL}/api/v4{path}",
        headers={"PRIVATE-TOKEN": token},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        console.print(
            Panel.fit(
                f"[bold red]✘ HTTP {e.code} Error[/bold red]\n"
                f"[dim]Response:[/dim] [yellow]{body}[/yellow]",
                title="[bold magenta]❌ API Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)


def api_post(path: str, token: str, data: bytes = b"") -> dict:
    req = urllib.request.Request(
        f"{GITLAB_URL}/api/v4{path}",
        data=data,
        headers={"PRIVATE-TOKEN": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        console.print(
            Panel.fit(
                f"[bold red]✘ HTTP {e.code} Error[/bold red]\n"
                f"[dim]Response:[/dim] [yellow]{body}[/yellow]",
                title="[bold magenta]❌ API Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)


def parse_url(url: str):
    """Extract project path and pipeline ID from a full GitLab pipeline URL."""
    pattern = r"https?://[^/]+/(.+)/-/pipelines/(\d+)"
    m = re.match(pattern, url)
    if not m:
        console.print(
            Panel.fit(
                f"[bold red]✘ Could not parse URL[/bold red]\n"
                f"[dim]URL:[/dim] [yellow]{url}[/yellow]",
                title="[bold magenta]❌ Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)
    return m.group(1), m.group(2)


# ── reusable pipeline helpers (used by cron.py and main) ────────────────────

def fetch_pipeline(encoded_project: str, pipeline_id: str, token: str) -> dict:
    """Fetch pipeline metadata from the GitLab API."""
    return api_get(f"/projects/{encoded_project}/pipelines/{pipeline_id}", token)


def fetch_jobs(encoded_project: str, pipeline_id: str, token: str) -> list:
    """Fetch all jobs for a pipeline (up to 100)."""
    return api_get(
        f"/projects/{encoded_project}/pipelines/{pipeline_id}/jobs?per_page=100",
        token,
    )


def get_pending_deploy_jobs(jobs: list) -> list:
    """Return jobs whose name contains 'deploy' and status is 'manual'."""
    return [
        j for j in jobs
        if "deploy" in j.get("name", "").lower() and j.get("status") in ("manual", "scheduled","canceled")
    ]


def requires_manual_deployment(jobs: list) -> bool:
    """Return True when at least one deploy job is waiting for manual action."""
    return bool(get_pending_deploy_jobs(jobs))


def trigger_manual_jobs(
    encoded_project: str, jobs: list, token: str, *, verbose: bool = True
) -> list[tuple[dict, dict]]:
    """Trigger every job in *jobs* via the GitLab play API.

    Returns a list of (job, api_result) tuples.
    """
    results = []
    for job in jobs:
        job_id = job["id"]
        job_name = job.get("name", str(job_id))
        if verbose:
            console.print(
                f"  [bold cyan]▶️[/bold cyan] [dim]Triggering manual job[/dim] [yellow]'{job_name}'[/yellow] [dim](#{job_id})[/dim]"
            )
        result = api_post(f"/projects/{encoded_project}/jobs/{job_id}/play", token)
        new_status = result.get("status", "unknown")
        icon = STATUS_ICONS.get(new_status, "❓")
        if verbose:
            console.print(
                f"  [bold green]✓[/bold green] [dim]Job[/dim] [yellow]'{job_name}'[/yellow] [dim]is now:[/dim] {icon} [cyan]{new_status}[/cyan]"
            )
        results.append((job, result))
    return results


def fmt_job(job: dict) -> str:
    """Format a single job dict as a printable line."""
    s = job.get("status", "unknown")
    ic = STATUS_ICONS.get(s, "❓")
    name = job.get("name", "")
    stage = job.get("stage", "")
    dur = job.get("duration")
    dur_str = ""
    if dur is not None:
        m, sec = divmod(int(dur), 60)
        dur_str = f"  ({m}m {sec}s)"
    return f"   {ic} [{stage}] {name}  →  {s}{dur_str}"


def main():
    parser = argparse.ArgumentParser(description="Check a GitLab pipeline status")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Full pipeline URL (alternative to --project + --pipeline-id)")
    group.add_argument("--project", help="Project path (e.g. adc/backends/project-name) or numeric ID", default="adc/backends/project-name")
    group.add_argument("--latest", action="store_true", help="Use the most recently triggered pipeline from pipeline.json")
    group.add_argument("--list", dest="list_records", action="store_true", help="List all pipeline records from pipeline.json and exit")
    parser.add_argument("--pipeline-id", help="Pipeline ID (required when using --project)")
    parser.add_argument("--manual-deploy", action="store_true", help="Trigger any deploy jobs that are waiting for manual action")
    args = parser.parse_args()

    # ── list mode: no token needed ───────────────────────────────────────────
    if args.list_records:
        Pipeline.list_all(verbose=True)
        return

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

    if args.latest:
        record = Pipeline.read_latest()
        if not record:
            console.print(
                Panel.fit(
                    "[bold red]✘ pipeline.json is empty — trigger a pipeline or MR first.[/bold red]",
                    title="[bold magenta]⚠️ Error[/bold magenta]",
                    border_style="red",
                    box=box.DOUBLE_EDGE,
                )
            )
            sys.exit(1)
        project, pipeline_id = record["project_path"], record["pipeline_id"]
        console.print(
            Panel.fit(
                f"[bold cyan]Using latest record[/bold cyan]\n"
                f"[dim]project:[/dim] [yellow]{project}[/yellow]\n"
                f"[dim]id:[/dim] [green]{pipeline_id}[/green]",
                title="[bold magenta]📋 Latest Record[/bold magenta]",
                border_style="cyan",
                box=box.DOUBLE_EDGE,
            )
        )
    elif args.url:
        project, pipeline_id = parse_url(args.url)
    else:
        if not args.pipeline_id:
            parser.error("--pipeline-id is required when using --project")
        project = args.project
        pipeline_id = args.pipeline_id

    encoded_project = urllib.parse.quote(project, safe="")

    pipeline = fetch_pipeline(encoded_project, pipeline_id, token)

    status = pipeline.get("status", "unknown")
    icon = STATUS_ICONS.get(status, "❓")
    web_url = pipeline.get("web_url", "")
    ref = pipeline.get("ref", "")
    sha = pipeline.get("sha", "")[:8]
    created_at = pipeline.get("created_at", "")
    duration = pipeline.get("duration")

    console.print(
        Panel.fit(
            f"[bold cyan]Pipeline #{pipeline_id}[/bold cyan]\n"
            f"[dim]Status:[/dim] {icon} [yellow]{status}[/yellow]\n"
            f"[dim]Branch:[/dim] [green]{ref}[/green]\n"
            f"[dim]Commit:[/dim] [blue]{sha}[/blue]\n"
            f"[dim]Created:[/dim] [dim]{created_at}[/dim]",
            title="[bold magenta]🔍 Pipeline Status[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    if duration is not None:
        mins, secs = divmod(int(duration), 60)
        console.print(f"  [dim]Duration:[/dim] [green]{mins}m {secs}s[/green]")
    console.print(f"  [dim]URL:[/dim] [blue underline]{web_url}[/blue underline]")

    # ── Jobs ───────────────────────────────────────────────────────────────
    jobs = fetch_jobs(encoded_project, pipeline_id, token)

    pending = get_pending_deploy_jobs(jobs)

    table = Table(
        title="[bold]Jobs Summary[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        show_lines=False,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Name", style="white")
    table.add_column("Stage", style="yellow", no_wrap=True)
    table.add_column("Status", style="green", no_wrap=True)
    table.add_column("Duration", style="dim", no_wrap=True)

    for i, job in enumerate(jobs, 1):
        job_status = job.get("status", "unknown")
        job_icon = STATUS_ICONS.get(job_status, "❓")
        dur = job.get("duration")
        dur_str = f"{int(dur // 60)}m {int(dur % 60)}s" if dur else "-"
        table.add_row(
            str(i),
            job.get("name", "?")[:40],
            job.get("stage", "?"),
            f"{job_icon} {job_status}",
            dur_str,
        )

    console.print(table)

    if pending:
        console.print(
            f"\n[bold magenta]── Manual Deploy Jobs ─────────────────────────────────────────────[/bold magenta]"
        )
        for job in pending:
            console.print(fmt_job(job))

        if args.manual_deploy:
            trigger_manual_jobs(encoded_project, pending, token)

    console.print()


if __name__ == "__main__":
    main()