import json
import os
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

_JSON_PATH = os.path.join(os.path.dirname(__file__), "pipeline.json")


# ── low-level helpers ────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(_JSON_PATH):
        return []
    with open(_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{_JSON_PATH} must contain a JSON array at the top level")
    return data


def _save(records: list[dict]) -> None:
    with open(_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")


def create_from_mr(
    project_path: str,
    branch: str,
    source_branch: str,
    title: str,
    web_url: str,
    merge_request_iid: int,
    state: str,
) -> dict:
    """Append a new merge request record and return it."""
    record = {
        "type": "merge_request",
        "project_path": project_path,
        "branch": branch,
        "source_branch": source_branch,
        "title": title,
        "web_url": web_url,
        "merge_request_iid": merge_request_iid,
        "state": state,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    records = _load()
    records.append(record)
    _save(records)
    return record


# ── public API ───────────────────────────────────────────────────────────────

def create(
    pipeline_id: str,
    project_path: str,
    branch: str,
    web_url: str,
    variables: dict
) -> dict:
    """Append a new pipeline record and return it."""
    record = {
        "pipeline_id": str(pipeline_id),
        "project_path": project_path,
        "branch": branch,
        "web_url": web_url,
        "variables": variables,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
    records = _load()
    records.append(record)
    _save(records)
    return record


def read_all() -> list[dict]:
    """Return every pipeline record."""
    return _load()


def read_by_id(pipeline_id: str) -> Optional[dict]:
    """Return the first record matching pipeline_id, or None."""
    pid = str(pipeline_id)
    for record in _load():
        if record.get("pipeline_id") == pid:
            return record
    return None


def read_latest() -> Optional[dict]:
    """Return the most recently triggered pipeline record, or None."""
    records = _load()
    return records[-1] if records else None


def delete(pipeline_id: str) -> bool:
    """Remove the record with the given pipeline_id.

    Returns True if a record was deleted, False if not found.
    """
    pid = str(pipeline_id)
    records = _load()
    new_records = [r for r in records if r.get("pipeline_id") != pid]
    if len(new_records) == len(records):
        return False
    _save(new_records)
    return True


def increment_attempts(pipeline_id: str) -> Optional[int]:
    """Increment the attempts counter for the given pipeline_id and return the new value.

    The field defaults to 0 if absent. Returns None if the record is not found.
    """
    pid = str(pipeline_id)
    records = _load()
    for record in records:
        if record.get("pipeline_id") == pid:
            attempts = record.get("attempts", 0) + 1
            record["attempts"] = attempts
            _save(records)
            return attempts
    return None  # record not found


def list_all(verbose: bool = False) -> None:
    """Print a human-readable table of all stored pipeline records."""
    records = _load()
    if not records:
        console.print(
            Panel.fit(
                "[dim](no pipeline records)[/dim]",
                title="[bold magenta]📋 Pipeline Records[/bold magenta]",
                border_style="magenta",
                box=box.DOUBLE_EDGE,
            )
        )
        return

    STATUS_ICONS = {
        "success": "✅", "failed": "❌", "running": "🔄", "pending": "⏳",
        "canceled": "🚫", "skipped": "⏭️", "manual": "🖐️", "created": "🆕",
    }

    table = Table(
        title="[bold]Pipeline Records[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        show_lines=False,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Pipeline ID", style="white", no_wrap=True)
    table.add_column("Status", style="yellow", no_wrap=True)
    table.add_column("Branch", style="green", no_wrap=True)
    table.add_column("Project", style="blue")
    table.add_column("Triggered At", style="dim", no_wrap=True)

    for i, r in enumerate(records, 1):
        record_type = r.get("type", "pipeline")
        if record_type == "merge_request":
            mr_state = r.get("state", "?")
            mr_icon = "🟢" if mr_state == "opened" else "🔴" if mr_state == "closed" else "⚪"
            source = r.get("source_branch", "?")[:20]
            table.add_row(
                str(i),
                f"MR !{r.get('merge_request_iid', '?')}",
                f"{mr_icon} {mr_state}",
                f"→ {r.get('branch', '?')}",
                f"← {source}",
                r.get("project_path", "?")[:40],
                r.get("created_at", "?")[:19],
            )
        else:
            status = r.get("status", "?")
            icon = STATUS_ICONS.get(status, "❓")
            table.add_row(
                str(i),
                r.get("pipeline_id", "?"),
                f"{icon} {status}",
                r.get("branch", "?"),
                "-",
                r.get("project_path", "?")[:40],
                r.get("triggered_at", "?")[:19],
            )

    console.print(table)

    if verbose:
        console.print("\n[bold]Detailed Information:[/bold]")
        for r in records:
            console.print(
                Panel.fit(
                    f"[bold cyan]Pipeline #{r.get('pipeline_id', '?')}[/bold cyan]\n"
                    f"[dim]URL:[/dim] [blue]{r.get('web_url', '')}[/blue]\n"
                    f"[dim]Variables:[/dim] [yellow]{r.get('variables', {})}[/yellow]",
                    title="[bold magenta]📝 Details[/bold magenta]",
                    border_style="magenta",
                    box=box.DOUBLE_EDGE,
                )
            )