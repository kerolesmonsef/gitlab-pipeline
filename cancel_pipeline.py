#!/usr/bin/env python3
"""
Cancel a GitLab Pipeline by URL.

Usage:
    python cancel_pipeline.py --url "https://git.foo.mobi/group/project/-/pipelines/123"
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()
import urllib.parse

from rich.console import Console
from rich.panel import Panel
from rich import box

import Pipeline
import pipeline_status as ps

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Cancel a GitLab pipeline")
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

    project, pipeline_id = ps.parse_url(args.url)
    encoded_project = urllib.parse.quote(project, safe="")

    console.print(
        Panel.fit(
            f"[bold cyan]Cancelling pipeline[/bold cyan]\n"
            f"[dim]Project:[/dim] [yellow]{project}[/yellow]\n"
            f"[dim]Pipeline ID:[/dim] [cyan]#{pipeline_id}[/cyan]",
            title="[bold magenta]🚫 Cancel Pipeline[/bold magenta]",
            border_style="yellow",
            box=box.DOUBLE_EDGE,
        )
    )

    result = ps.api_post(
        f"/projects/{encoded_project}/pipelines/{pipeline_id}/cancel",
        token,
    )

    new_status = result.get("status", "unknown")
    icon = ps.STATUS_ICONS.get(new_status, "❓")
    web_url = result.get("web_url", args.url)

    console.print(
        Panel.fit(
            f"[bold green]✓ Pipeline cancelled[/bold green]\n"
            f"[dim]Status:[/dim] {icon} [yellow]{new_status}[/yellow]\n"
            f"[dim]URL:[/dim] [blue underline]{web_url}[/blue underline]",
            title="[bold magenta]✅ Done[/bold magenta]",
            border_style="green",
            box=box.DOUBLE_EDGE,
        )
    )

    deleted = Pipeline.delete(pipeline_id)
    if deleted:
        console.print(
            f"[bold green]✓[/bold green] [dim]Record removed from pipeline.json[/dim] [cyan](id={pipeline_id})[/cyan]"
        )
    else:
        console.print(
            f"[dim]ℹ️  No matching record found in pipeline.json[/dim]"
        )


if __name__ == "__main__":
    main()