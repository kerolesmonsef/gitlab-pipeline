import argparse
import os
import sys
import urllib.parse
import urllib.request
import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import Pipeline

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Trigger a GitLab pipeline")
    parser.add_argument("--project-path", default="adc/backends/project-name")
    parser.add_argument("--branch", default="staging")
    parser.add_argument("--deploy", default="true")
    parser.add_argument("--postman-tests", default="false")
    parser.add_argument("--sonar-tests", default="false")
    parser.add_argument("--jmeter-load-test", default="false")
    parser.add_argument("--jmeter-internal", default="false")
    parser.add_argument("--jmeter-external", default="false")
    parser.add_argument("--docker-cache", default="false")
    args = parser.parse_args()

    gitlab_url = "https://git.foo.mobi"
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

    project_path = urllib.parse.quote(args.project_path, safe="")

    console.print(
        Panel.fit(
            f"[bold cyan]trigger_pipeline[/bold cyan] called\n"
            f"[dim]project:[/dim] [yellow]{args.project_path}[/yellow]\n"
            f"[dim]branch:[/dim] [green]{args.branch}[/green]\n"
            f"[dim]deploy:[/dim] [blue]{args.deploy}[/blue]",
            title="[bold magenta]⚡ Tool Invoked[/bold magenta]",
            border_style="magenta",
            box=box.DOUBLE_EDGE,
        )
    )

    payload = json.dumps({
        "ref": f"refs/heads/{args.branch}",
        "variables": [
            {"key": "DEPLOY", "value": args.deploy},
            {"key": "POSTMAN_TESTS", "value": args.postman_tests},
            {"key": "SONAR_TESTS", "value": args.sonar_tests},
            {"key": "JMETER_LOAD_TEST", "value": args.jmeter_load_test},
            {"key": "JMETER_INTERNAL", "value": args.jmeter_internal},
            {"key": "JMETER_EXTERNAL", "value": args.jmeter_external},
            {"key": "DOCKER_CACHE", "value": args.docker_cache},
        ],
    }).encode()

    req = urllib.request.Request(
        f"{gitlab_url}/api/v4/projects/{project_path}/pipeline",
        data=payload,
        headers={
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode())
            console.print(
                Panel.fit(
                    f"[bold green]✓ Pipeline created successfully[/bold green]\n"
                    f"[dim]URL:[/dim] [blue underline]{body['web_url']}[/blue underline]\n"
                    f"[dim]ID:[/dim] [yellow]{body['id']}[/yellow]",
                    title="[bold magenta]🚀 Pipeline Created[/bold magenta]",
                    border_style="green",
                    box=box.DOUBLE_EDGE,
                )
            )

            Pipeline.create(
                pipeline_id=str(body["id"]),
                project_path=args.project_path,
                branch=args.branch,
                web_url=body["web_url"],
                variables={
                    "DEPLOY": args.deploy,
                    "POSTMAN_TESTS": args.postman_tests,
                    "SONAR_TESTS": args.sonar_tests,
                    "JMETER_LOAD_TEST": args.jmeter_load_test,
                    "JMETER_INTERNAL": args.jmeter_internal,
                    "JMETER_EXTERNAL": args.jmeter_external,
                    "DOCKER_CACHE": args.docker_cache,
                }
            )

            console.print(
                f"[bold green]✓[/bold green] [dim]Record saved to pipeline.json[/dim] [cyan](id={body['id']})[/cyan]"
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        console.print(
            Panel.fit(
                f"[bold red]✘ HTTP {e.code} Error[/bold red]\n"
                f"[dim]Response:[/dim] [yellow]{body}[/yellow]",
                title="[bold magenta]❌ Pipeline Failed[/bold magenta]",
                border_style="red",
                box=box.DOUBLE_EDGE,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()