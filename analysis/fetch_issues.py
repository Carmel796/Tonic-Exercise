#!/usr/bin/env python3
import os, json, requests, argparse, sys
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ----------------- Config -----------------
BASE  = os.getenv("JIRA_BASE_URL", "").rstrip("/")
EMAIL = os.getenv("JIRA_EMAIL")
TOKEN = os.getenv("JIRA_API_TOKEN")

auth = HTTPBasicAuth(EMAIL, TOKEN)
headers = {"Content-Type": "application/json", "Accept": "application/json"}

# ----------------- Output dir (for partial + checkpoint only) -----------------
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------- IO paths (defaults) -----------------
DEFAULT_OUT_JSON   = "issues_data.json"
DEFAULT_PARTIAL    = OUTPUT_DIR / "issues_partial.jsonl"
DEFAULT_CHECKPOINT = OUTPUT_DIR / "fetch_checkpoint.json"

# ----------------- Helpers -----------------
def _post(session, url, payload):
    r = session.post(url, json=payload, timeout=60)
    # For debugging 4xx/5xx while still raising:
    if r.status_code >= 400:
        try:
            errj = r.json()
            print(f"❌ HTTP {r.status_code} response: {errj}")
        except Exception:
            print(f"❌ HTTP {r.status_code} text: {r.text}")
    r.raise_for_status()
    return r.json()

def adf_to_text(adf: dict) -> str:
    """Convert Jira ADF document to plain text with paragraph breaks."""
    if not adf:
        return ""
    lines = []
    for node in adf.get("content", []):
        if node.get("type") == "paragraph":
            paragraph = ""
            for child in node.get("content", []):
                if child.get("type") == "text":
                    paragraph += child.get("text", "")
                elif child.get("type") == "hardBreak":
                    paragraph += "\n"
            lines.append(paragraph.strip())
    return "\n\n".join(lines).strip()

def read_checkpoint(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_checkpoint(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def load_saved_keys(partial_path: Path):
    """Return (saved_keys, saved_count)."""
    saved_keys = set()
    count = 0
    if partial_path.exists():
        with partial_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    k = obj.get("key")
                    if k:
                        saved_keys.add(k)
                        count += 1
                except Exception:
                    continue
    return saved_keys, count

def append_issue(partial_path: Path, issue_obj: dict):
    with partial_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(issue_obj, ensure_ascii=False) + "\n")
        f.flush()

def materialize_json_from_jsonl(partial_path: Path, out_json: Path):
    items = []
    if partial_path.exists():
        with partial_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
    out_json.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(items)

# ----------------- Core fetcher (resumable) -----------------
def fetch_all_basic_resumable(
    jql: str,
    page_size: int,
    partial_path: Path,
    checkpoint_path: Path,
    try_use_checkpoint_token: bool = True,
):
    """
    Fault-tolerant fetch:
    - Appends each issue to JSONL (partial_path)
    - Saves checkpoint with nextPageToken after each page
    - Resumes from checkpoint; if token invalid, restarts from beginning & dedups
    """
    url = f"{BASE}/rest/api/3/search/jql"
    # Load already-saved keys (dedup across restarts or fallback runs)
    saved_keys, saved_count = load_saved_keys(partial_path)
    print(f"🧾 Found {saved_count} already saved issues ({len(saved_keys)} unique keys)")

    checkpoint = read_checkpoint(checkpoint_path)
    token = checkpoint.get("nextPageToken") if (try_use_checkpoint_token and checkpoint) else None

    with requests.Session() as s:
        s.auth = auth
        s.headers.update(headers)

        page_index = 0
        while True:
            payload = {
                "jql": jql,
                "maxResults": page_size,
                "fields": ["issuetype", "summary", "description"]
            }
            if token:
                payload["nextPageToken"] = token

            try:
                data = _post(s, url, payload)
            except requests.HTTPError as e:
                # If we tried to use a stored nextPageToken and it failed (400),
                # fallback: restart from beginning, dedup via saved_keys
                if token is not None:
                    print("⚠️ nextPageToken failed; falling back to restart-from-beginning with dedup.")
                    token = None
                    continue
                raise e  # real error on a fresh start

            issues = data.get("issues", [])
            if not issues:
                print("No more issues in response page.")
                break

            new_in_page = 0
            for issue in issues:
                fields = issue.get("fields", {})
                obj = {
                    "key": issue.get("key"),
                    "type": (fields.get("issuetype") or {}).get("name"),
                    "summary": fields.get("summary") or "",
                    "description": adf_to_text(fields.get("description")),
                }
                k = obj["key"]
                if not k:
                    continue
                if k in saved_keys:
                    # already written previously — skip duplicate
                    continue
                append_issue(partial_path, obj)
                saved_keys.add(k)
                new_in_page += 1

            page_index += 1
            print(f"📦 Page {page_index}: saved {new_in_page} new issues (total unique so far: {len(saved_keys)})")

            # checkpoint
            token = data.get("nextPageToken")
            write_checkpoint(checkpoint_path, {
                "jql": jql,
                "page_size": page_size,
                "nextPageToken": token,
                "saved_unique": len(saved_keys),
                "page_index": page_index,
                "isLast": data.get("isLast", False),
            })

            if data.get("isLast"):
                print("✅ isLast=true — finished pagination.")
                break

# ----------------- High-level wrapper -----------------
def fetch_and_save(
    project_key: str,
    out_path: str = DEFAULT_OUT_JSON,
    page_size: int = 100,
    jql_suffix: str = "ORDER BY created DESC",
    partial_path: str = DEFAULT_PARTIAL,
    checkpoint_path: str = DEFAULT_CHECKPOINT,
):
    """
    Resumable wrapper:
    - Fetch & append issues to JSONL
    - Update checkpoint after every page
    - Build final JSON at the end
    """
    if not BASE or not EMAIL or not TOKEN:
        raise RuntimeError("Missing Jira credentials in environment (.env).")

    jql = f"project = {project_key} {jql_suffix}".strip()
    print(f"🔍 Fetching issues for project '{project_key}' with page_size={page_size}")
    print(f"JQL: {jql}")

    partial = Path(partial_path)
    checkpoint = Path(checkpoint_path)
    out_json = Path(out_path)

    try:
        fetch_all_basic_resumable(
            jql=jql,
            page_size=page_size,
            partial_path=partial,
            checkpoint_path=checkpoint,
            try_use_checkpoint_token=True,
        )
    except KeyboardInterrupt:
        print("\n🟡 Interrupted. Partial data and checkpoint preserved. Re-run to resume.")
        sys.exit(130)

    # Materialize final JSON from JSONL (idempotent)
    total = materialize_json_from_jsonl(partial, out_json)
    print(f"🧩 Materialized {total} issues into {out_json}")

# ----------------- CLI entrypoint -----------------
def main():
    parser = argparse.ArgumentParser(description="Fault-tolerant Jira issues fetcher.")
    parser.add_argument("--project", default="TON", help="Jira project key, e.g. TON")
    parser.add_argument("--out", default=DEFAULT_OUT_JSON, help="Output JSON file path")
    parser.add_argument("--partial", default=DEFAULT_PARTIAL, help="Partial JSONL path (append-only)")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT, help="Checkpoint JSON path")
    parser.add_argument("--page-size", type=int, default=10, help="Page size per Jira API call (max 100)")
    parser.add_argument("--jql-suffix", default="ORDER BY created DESC", help="Optional JQL suffix for sorting/filtering")
    args = parser.parse_args()

    fetch_and_save(
        project_key=args.project,
        out_path=args.out,
        page_size=args.page_size,
        jql_suffix=args.jql_suffix,
        partial_path=args.partial,
        checkpoint_path=args.checkpoint,
    )

if __name__ == "__main__":
    main()
