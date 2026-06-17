#!/usr/bin/env python3
"""
Track a GitLab Merge Request by URL.

Usage:
    python mr_track.py --url "https://git.foo.mobi/group/project/-/merge_requests/123"

When the MR merges, cron.py detects it, extracts the post-merge pipeline,
and adds it to pipeline.json for auto-deploy handling.
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
import json

from rich.console import Console
from rich.panel import Panel
from rich import box

import MR

console = Console()

GITLAB_URL = "https://git.foo.mobi"


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


def parse_mr_url(url: str) -> tuple[str, int]:
    """Extract project path and MR IID from a GitLab MR URL.

    Expected format: https://git.foo.mobi/group/project/-/merge_requests/123
    """
    pattern = r"https?://[^/]+/(.+)/-/merge_requests/(\d+)"
    m = re.match(pattern, url)
    if not m:
        console.print(
            Panel.fit(
                f"[bold red]✘ Could not parse MR URL[/bold red]\n"
                f"[dim]URL:[/dim] [yellow]{url}[/yellow]\n"
                f"[dim]Expected:[/dim] [cyan]https://git.foo.mobi/group/project/-/merge_requests/123[/cyan]",
                title="[bold magenta]❌ Invalid URL[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)
    return m.group(1), int(m.group(2))


def main():
    parser = argparse.ArgumentParser(description="Track a GitLab Merge Request by URL")
    parser.add_argument(
        "--url",
        required=True,
        help="Full GitLab MR URL (e.g. https://git.foo.mobi/group/project/-/merge_requests/123)",
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

    project_path, mr_iid = parse_mr_url(args.url)
    encoded_project = urllib.parse.quote(project_path, safe="")

    mr = api_get(f"/projects/{encoded_project}/merge_requests/{mr_iid}", token)

    state = mr.get("state", "unknown")
    title = mr.get("title", "")
    source_branch = mr.get("source_branch", "")
    target_branch = mr.get("target_branch", "")
    web_url = mr.get("web_url", args.url)

    STATE_ICONS = {"opened": "🟢", "merged": "🟣", "closed": "🔴"}
    icon = STATE_ICONS.get(state, "⚪")

    console.print(
        Panel.fit(
            f"[bold cyan]MR !{mr_iid}[/bold cyan]\n"
            f"[dim]Title:[/dim] [white]{title[:60]}[/white]\n"
            f"[dim]State:[/dim] {icon} [yellow]{state}[/yellow]\n"
            f"[dim]Source:[/dim] [green]{source_branch}[/green]\n"
            f"[dim]Target:[/dim] [blue]{target_branch}[/blue]",
            title="[bold magenta]🔀 Merge Request[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    if state == "merged":
        console.print(
            Panel.fit(
                "[bold yellow]⚠️ MR is already merged.[/bold yellow]\n"
                "[dim]Use mr_track.py only for open MRs you want to watch.[/dim]",
                title="[bold magenta]ℹ️ Info[/bold magenta]",
                border_style="yellow",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(0)

    if state == "closed":
        console.print(
            Panel.fit(
                "[bold red]✘ MR is closed — nothing to track.[/bold red]",
                title="[bold magenta]⚠️ Warning[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(0)

    record = MR.create(
        project_path=project_path,
        mr_iid=mr_iid,
        web_url=web_url,
        title=title,
        source_branch=source_branch,
        target_branch=target_branch,
    )

    console.print(
        Panel.fit(
            f"[bold green]✓ MR record saved to mr.json[/bold green]\n"
            f"[dim]Project:[/dim] [yellow]{project_path}[/yellow]\n"
            f"[dim]MR IID:[/dim] [cyan]!{mr_iid}[/cyan]\n"
            f"[dim]Watching:[/dim] [green]{source_branch}[/green] → [blue]{target_branch}[/blue]\n"
            f"[dim]cron.py will detect merge and hand off pipeline automatically.[/dim]",
            title="[bold magenta]💾 Tracking Started[/bold magenta]",
            border_style="green",
            box=box.DOUBLE_EDGE,
        )
    )


if __name__ == "__main__":
    main()
