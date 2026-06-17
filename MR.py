import json
import os
from datetime import datetime, timezone
from typing import Optional

_JSON_PATH = os.path.join(os.path.dirname(__file__), "mr.json")


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


def create(
    project_path: str,
    mr_iid: int,
    web_url: str,
    title: str,
    source_branch: str,
    target_branch: str,
) -> dict:
    record = {
        "project_path": project_path,
        "mr_iid": int(mr_iid),
        "web_url": web_url,
        "title": title,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "tracked_at": datetime.now(timezone.utc).isoformat(),
        "attempts": 0,
    }
    records = _load()
    records.append(record)
    _save(records)
    return record


def read_all() -> list[dict]:
    return _load()


def delete(project_path: str, mr_iid: int) -> bool:
    iid = int(mr_iid)
    records = _load()
    new_records = [
        r for r in records
        if not (r.get("project_path") == project_path and int(r.get("mr_iid", -1)) == iid)
    ]
    if len(new_records) == len(records):
        return False
    _save(new_records)
    return True


def increment_attempts(project_path: str, mr_iid: int) -> Optional[int]:
    iid = int(mr_iid)
    records = _load()
    for record in records:
        if record.get("project_path") == project_path and int(record.get("mr_iid", -1)) == iid:
            attempts = record.get("attempts", 0) + 1
            record["attempts"] = attempts
            _save(records)
            return attempts
    return None
