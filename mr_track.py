#!/usr/bin/env python3
"""
Track a GitLab Pipeline by URL.

Usage:
    python mr_track.py --url "https://git.foo.mobi/group/project/-/pipelines/123"
"""

import argparse
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
from rich import box

import Pipeline
import pipeline_status as ps


console = Console()

GITLAB_URL = "https://git.foo.mobi"


def api_get(path: str, token: str) -> dict:
    """Make an authenticated GET request to the GitLab API."""
    req = urllib.request.Request(
        f"{GITLAB_URL}/api/v4{path}",
        headers={"PRIVATE-TOKEN": token},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return __import__("json").loads(resp.read().decode())
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


def parse_pipeline_url(url: str) -> tuple[str, int]:
    """Extract project path and pipeline ID from a full GitLab pipeline URL.

    URL format: https://git.foo.mobi/group/project/-/pipelines/123

    Returns:
        tuple of (project_path, pipeline_id)
    """
    pattern = r"https?://[^/]+/(.+)/-/pipelines/(\d+)"
    m = re.match(pattern, url)
    if not m:
        console.print(
            Panel.fit(
                f"[bold red]✘ Could not parse Pipeline URL[/bold red]\n"
                f"[dim]URL:[/dim] [yellow]{url}[/yellow]\n"
                f"[dim]Expected format:[/dim] [cyan]https://git.foo.mobi/group/project/-/pipelines/123[/cyan]",
                title="[bold magenta]❌ Invalid URL[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)
    return m.group(1), int(m.group(2))


def fetch_pipeline_details(project_path: str, pipeline_id: int, token: str) -> dict:
    """Fetch pipeline details from GitLab API."""
    encoded_project = urllib.parse.quote(project_path, safe="")
    return api_get(f"/projects/{encoded_project}/pipelines/{pipeline_id}", token)


def main():
    parser = argparse.ArgumentParser(description="Track a GitLab Pipeline by URL")
    parser.add_argument(
        "--url",
        required=True,
        help="Full GitLab pipeline URL (e.g. https://git.foo.mobi/group/project/-/pipelines/123)",
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

    console.print(
        Panel.fit(
            f"[bold cyan]Parsing Pipeline URL[/bold cyan]\n"
            f"[dim]URL:[/dim] [blue]{args.url}[/blue]",
            title="[bold magenta]🔗 Processing[/bold magenta]",
            border_style="magenta",
            box=box.DOUBLE_EDGE,
        )
    )

    project_path, pipeline_id = parse_pipeline_url(args.url)

    console.print(
        f"[dim]Extracted project:[/dim] [yellow]{project_path}[/yellow]\n"
        f"[dim]Pipeline ID:[/dim] [cyan]{pipeline_id}[/cyan]"
    )

    console.print(
        f"\n[bold cyan]Fetching pipeline details from GitLab...[/bold cyan]"
    )

    pipeline = fetch_pipeline_details(project_path, pipeline_id, token)

    branch = pipeline.get("ref", "unknown")
    web_url = pipeline.get("web_url", args.url)
    status = pipeline.get("status", "unknown")
    sha = pipeline.get("sha", "")[:8]


    status_icon = ps.STATUS_ICONS.get(status, "❓")

    console.print(
        Panel.fit(
            f"[bold cyan]Pipeline #{pipeline_id}[/bold cyan]\n"
            f"[dim]Status:[/dim] {status_icon} [yellow]{status}[/yellow]\n"
            f"[dim]Branch:[/dim] [green]{branch}[/green]\n"
            f"[dim]Commit:[/dim] [blue]{sha}[/blue]",
            title="[bold magenta]📋 Pipeline Details[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    record = Pipeline.create(
        pipeline_id=str(pipeline_id),
        project_path=project_path,
        branch=branch,
        web_url=web_url,
        variables={},
    )

    console.print(
        Panel.fit(
            f"[bold green]✓ Pipeline record saved[/bold green]\n"
            f"[dim]Project:[/dim] [yellow]{project_path}[/yellow]\n"
            f"[dim]Pipeline:[/dim] [cyan]#{pipeline_id}[/cyan]",
            title="[bold magenta]💾 Record Saved[/bold magenta]",
            border_style="green",
            box=box.DOUBLE_EDGE,
        )
    )


if __name__ == "__main__":
    main()
