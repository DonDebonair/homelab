import json
import re
import urllib.request
from pathlib import Path

import cyclopts

from op_secrets import SecretString

n8n = cyclopts.App(name="n8n")

ROOT = Path(__file__).parent.parent.resolve()
WORKFLOWS_DIR = ROOT / "n8n" / "workflows"

BASE_URL = "https://n8n.dv.zone/api/v1"
API_KEY = SecretString("op://Homelab/n8n secrets/api key")

# Top-level fields worth versioning. Everything else is volatile (versionId,
# updatedAt, ...), runtime state (staticData, pinData) or ownership metadata
# (shared), and would only add noise to diffs.
KEEP_FIELDS = ("id", "name", "active", "nodes", "connections", "settings", "tags")


def _get(path: str) -> dict:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"X-N8N-API-KEY": str(API_KEY), "Accept": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def _list_workflows() -> list[dict]:
    workflows: list[dict] = []
    cursor = None
    while True:
        query = "?limit=100&excludePinnedData=true"
        if cursor:
            query += f"&cursor={cursor}"
        page = _get(f"/workflows{query}")
        workflows.extend(page["data"])
        cursor = page.get("nextCursor")
        if not cursor:
            return workflows


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _normalise(workflow: dict) -> dict:
    snapshot = {key: workflow[key] for key in KEEP_FIELDS if key in workflow}
    snapshot["tags"] = sorted(tag["name"] for tag in workflow.get("tags", []))
    return snapshot


@n8n.command
def export(*, dry_run: bool = False):
    """Snapshot all non-archived n8n workflows to n8n/workflows/<slug>.json.

    n8n stays the source of truth; this is for history and diffs. Files of
    workflows that no longer exist (deleted, archived or renamed) are removed.

    Parameters
    ----------
    dry_run
        Print which files would be written/removed without touching disk.
    """
    SecretString.populate_cache_sync()
    workflows = [w for w in _list_workflows() if not w.get("isArchived")]

    written: set[Path] = set()
    for workflow in sorted(workflows, key=lambda w: w["name"]):
        path = WORKFLOWS_DIR / f"{_slug(workflow['name'])}.json"
        if path in written:
            raise SystemExit(f"Two workflows map to {path.name}; rename one in n8n.")
        written.add(path)
        content = json.dumps(_normalise(workflow), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        print(f"write  {path.relative_to(ROOT)}  ({workflow['name']})")
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    for stale in sorted(set(WORKFLOWS_DIR.glob("*.json")) - written):
        print(f"remove {stale.relative_to(ROOT)}")
        if not dry_run:
            stale.unlink()
