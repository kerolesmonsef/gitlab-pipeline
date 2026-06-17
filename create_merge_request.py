#!/usr/bin/env python3
"""
Push current branch and create a GitLab MR, then auto-track it.

Usage:
    python create_merge_request.py --target staging
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

import MR

load_dotenv()

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
                f"[bold red]✘ HTTP {e.code}[/bold red]\n[yellow]{body}[/yellow]",
                title="[bold magenta]❌ API Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)


def current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        console.print(
            Panel.fit(
                "[bold red]✘ Not inside a git repo or HEAD detached.[/bold red]",
                title="[bold magenta]❌ Git Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)
    return branch


def run_git_push(branch: str, target: str) -> str:
    cmd = [
        "git", "push", "origin", branch,
        "-o", "merge_request.create",
        f"-o", f"merge_request.target={target}",
    ]

    console.print(
        Panel.fit(
            f"[dim]$[/dim] [cyan]{' '.join(cmd)}[/cyan]",
            title="[bold magenta]🚀 Running Git Push[/bold magenta]",
            border_style="blue",
            box=box.DOUBLE_EDGE,
        )
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    combined = result.stdout + result.stderr

    # Print raw git output inside a panel
    output_lines = combined.strip()
    console.print(
        Panel(
            f"[dim]{output_lines}[/dim]",
            title="[bold blue]📤 Git Output[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
        )
    )

    if result.returncode != 0:
        # Check if it's just "already up to date" or branch already exists — not fatal
        # if MR URL is present, treat as success
        if "View merge request" not in combined and "merge_requests" not in combined:
            console.print(
                Panel.fit(
                    f"[bold red]✘ git push failed (exit {result.returncode})[/bold red]",
                    title="[bold magenta]❌ Push Failed[/bold magenta]",
                    border_style="red",
                    box=box.DOUBLE_EDGE,
                )
            )
            sys.exit(1)

    return combined


def extract_mr_url(output: str) -> str | None:
    pattern = r"https://[^\s]+/-/merge_requests/\d+"
    m = re.search(pattern, output)
    return m.group(0) if m else None


def parse_mr_url(url: str) -> tuple[str, int]:
    pattern = r"https?://[^/]+/(.+)/-/merge_requests/(\d+)"
    m = re.match(pattern, url)
    if not m:
        console.print(
            Panel.fit(
                f"[bold red]✘ Could not parse MR URL:[/bold red] [yellow]{url}[/yellow]",
                title="[bold magenta]❌ Parse Error[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)
    return m.group(1), int(m.group(2))


def main():
    parser = argparse.ArgumentParser(description="Push branch, create MR, auto-track it")
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target branch for the MR (e.g. staging, main)",
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

    branch = current_branch()

    console.print(Rule("[bold cyan]Create & Track MR[/bold cyan]"))
    console.print(
        Panel.fit(
            f"[dim]Branch:[/dim]  [green]{branch}[/green]\n"
            f"[dim]Target:[/dim]  [blue]{args.target}[/blue]",
            title="[bold magenta]🔀 MR Details[/bold magenta]",
            border_style="cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    push_output = run_git_push(branch, args.target)

    mr_url = extract_mr_url(push_output)
    if not mr_url:
        console.print(
            Panel.fit(
                "[bold yellow]⚠️ No MR URL found in push output.[/bold yellow]\n"
                "[dim]MR may already exist or push was skipped.[/dim]",
                title="[bold magenta]ℹ️ No MR URL[/bold magenta]",
                border_style="yellow",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(0)

    console.print(
        Panel.fit(
            f"[bold green]✓ MR URL detected[/bold green]\n[cyan]{mr_url}[/cyan]",
            title="[bold magenta]🔗 MR Link[/bold magenta]",
            border_style="green",
            box=box.DOUBLE_EDGE,
        )
    )

    project_path, mr_iid = parse_mr_url(mr_url)
    encoded_project = urllib.parse.quote(project_path, safe="")

    console.print("[dim]Fetching MR details from GitLab API...[/dim]")
    mr = api_get(f"/projects/{encoded_project}/merge_requests/{mr_iid}", token)

    title = mr.get("title", "")
    source_branch = mr.get("source_branch", branch)
    target_branch = mr.get("target_branch", args.target)
    web_url = mr.get("web_url", mr_url)
    state = mr.get("state", "opened")

    if state in ("merged", "closed"):
        console.print(
            Panel.fit(
                f"[bold yellow]⚠️ MR is already {state} — skipping tracking.[/bold yellow]",
                title="[bold magenta]ℹ️ Info[/bold magenta]",
                border_style="yellow",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(0)

    MR.create(
        project_path=project_path,
        mr_iid=mr_iid,
        web_url=web_url,
        title=title,
        source_branch=source_branch,
        target_branch=target_branch,
    )

    console.print(Rule())
    console.print(
        Panel.fit(
            f"[bold green]✓ MR created and tracked![/bold green]\n\n"
            f"[dim]Title:[/dim]   [white]{title[:60]}[/white]\n"
            f"[dim]Project:[/dim] [yellow]{project_path}[/yellow]\n"
            f"[dim]MR IID:[/dim]  [cyan]!{mr_iid}[/cyan]\n"
            f"[dim]Watch:[/dim]   [green]{source_branch}[/green] → [blue]{target_branch}[/blue]\n"
            f"[dim]URL:[/dim]     [cyan]{web_url}[/cyan]\n\n"
            f"[dim]cron.py will detect merge and hand off pipeline automatically.[/dim]",
            title="[bold magenta]🎉 Done[/bold magenta]",
            border_style="green",
            box=box.DOUBLE_EDGE,
        )
    )


if __name__ == "__main__":
    main()
