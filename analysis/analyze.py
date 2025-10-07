#!/usr/bin/env python3
import os, re, json, time, sys
from collections import Counter
from pathlib import Path
from typing import List, Set, Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ----------------- Config -----------------
ISSUE_LIMIT = int(os.getenv("ISSUE_LIMIT", "0"))  # 0 = all
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or "meta-llama/llama-3.1-8b-instruct"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

TECH_LABELS = ["database", "networking", "authentication", "api", "storage"]
_ALLOWED = {l.lower() for l in TECH_LABELS}
UNCLASSIFIED_LABEL = "unclassified"  # kept out of _ALLOWED on purpose

# Output files
TECH_PER_ISSUE = OUTPUT_DIR / "technology_annotations.jsonl"
SERVERS_PER_ISSUE = OUTPUT_DIR / "server_mentions.jsonl"
TECH_COUNTS = OUTPUT_DIR / "technology_counts.jsonl"
SERVER_COUNTS = OUTPUT_DIR / "server_counts.jsonl"
UNRESOLVED_JSON = OUTPUT_DIR / "unresolved_servers_tickets.json"

# ----------------- Server extraction -----------------
SRV_REGEX = re.compile(r"\bsrv-[a-z0-9]{2,10}\b", flags=re.IGNORECASE)

def extract_servers(text: str) -> List[str]:
    if not text:
        return []
    return [m.group(0).lower() for m in SRV_REGEX.finditer(text)]

# ----------------- OpenRouter client -----------------
_client = None
def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", ""),
                "X-Title": os.getenv("OPENROUTER_X_TITLE", "Jira Tech Classifier"),
            },
        )
    return _client

TECH_PROMPT_SYSTEM = (
    "You are a precise, conservative classifier. "
    "Given an incident description, answer with EXACTLY ONE WORD that is one of the allowed labels. "
    "Do not add any other text."
)

def classify_technology(text: str) -> str:
    """Return exactly one of the allowed labels; retry once; else 'unclassified'."""
    if not (text and text.strip()):
        return UNCLASSIFIED_LABEL

    allowed_line = "Allowed labels: database, networking, authentication, api, storage"
    user_msg = (
        f"{allowed_line}\n\n"
        "Rules:\n"
        "- Reply with exactly one word from the allowed labels.\n"
        "- No punctuation, no quotes, no explanations.\n"
        "- If uncertain, pick the closest label.\n\n"
        f"TEXT:\n{text}"
    )

    client = get_client()

    def ask_once() -> str:
        resp = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": TECH_PROMPT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
        )
        raw = (resp.choices[0].message.content or "").strip().lower()
        return raw.strip("`\"' ").split()[0] if raw else ""

    try:
        label = ask_once()
        if label in _ALLOWED:
            return label
        time.sleep(0.6)
        label = ask_once()
        return label if label in _ALLOWED else UNCLASSIFIED_LABEL
    except Exception:
        return UNCLASSIFIED_LABEL

# ----------------- JSONL helpers -----------------
def load_processed_keys_from_jsonl(path: Path, key_field: str) -> Set[str]:
    keys: Set[str] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            if obj.get(key_field):
                keys.add(obj[key_field])
        except Exception:
            continue
    return keys

def append_jsonl(path: Path, obj: Dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()

# ----------------- Aggregation -----------------
def aggregate_outputs(issues_all: List[Dict]):
    """Rebuild counts + unresolved outputs from per-issue logs."""
    tech_counter = Counter()
    if TECH_PER_ISSUE.exists():
        for line in TECH_PER_ISSUE.read_text(encoding="utf-8").splitlines():
            try:
                label = json.loads(line).get("label")
                if label:
                    tech_counter.update([label])
            except Exception:
                continue
    with TECH_COUNTS.open("w", encoding="utf-8") as f:
        for tech, cnt in tech_counter.most_common():
            f.write(json.dumps({"technology": tech, "count": cnt}, ensure_ascii=False) + "\n")

    server_counter = Counter()
    keys_with_servers = set()
    if SERVERS_PER_ISSUE.exists():
        for line in SERVERS_PER_ISSUE.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
                key, servers = obj.get("key"), obj.get("servers", [])
                if servers:
                    keys_with_servers.add(key)
                    server_counter.update(servers)
            except Exception:
                continue

    with SERVER_COUNTS.open("w", encoding="utf-8") as f:
        for server, cnt in server_counter.most_common():
            f.write(json.dumps({"server": server, "count": cnt}, ensure_ascii=False) + "\n")

    unresolved = [
        {"key": i.get("key"), "summary": i.get("summary") or ""}
        for i in issues_all if i.get("key") not in keys_with_servers
    ]
    UNRESOLVED_JSON.write_text(json.dumps(unresolved, ensure_ascii=False, indent=2), encoding="utf-8")

# ----------------- Main Function -----------------
def main(file_path="issues_data.json"):
    """Main entrypoint for analysis (resumable + fault tolerant)."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"{file_path} not found")

    issues_all = json.loads(p.read_text(encoding="utf-8"))
    issues = issues_all[:ISSUE_LIMIT] if ISSUE_LIMIT > 0 else issues_all

    processed_tech = load_processed_keys_from_jsonl(TECH_PER_ISSUE, "key")
    processed_servers = load_processed_keys_from_jsonl(SERVERS_PER_ISSUE, "key")
    processed_complete = processed_tech & processed_servers

    print(f"Loaded {len(issues)} issues. Already complete: {len(processed_complete)}")
    processed_this_run = 0

    try:
        for idx, issue in enumerate(issues, 1):
            key, summary, desc = issue.get("key"), issue.get("summary", ""), issue.get("description", "")
            if key in processed_complete:
                if idx % 250 == 0:
                    print(f"[{idx}/{len(issues)}] Skipped {key}")
                continue

            text = f"{summary}\n{desc}".strip()
            print(f"[{idx}/{len(issues)}] Processing {key}...")

            servers = extract_servers(text)
            append_jsonl(SERVERS_PER_ISSUE, {"key": key, "servers": servers})

            label = classify_technology(text)
            append_jsonl(TECH_PER_ISSUE, {"key": key, "label": label})

            processed_this_run += 1
            if processed_this_run % 25 == 0:
                print(f"↳ Processed {processed_this_run} new issues")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted, finalizing partial aggregates...")
    except Exception as e:
        print(f"\n❌ Error: {e}\nFinalizing partial aggregates...")

    aggregate_outputs(issues_all)

    print("\n=== Analysis Complete ===")
    print(f"Artifacts written to: {OUTPUT_DIR.resolve()}")

# ----------------- Entrypoint -----------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze Jira issues for servers and technologies.")
    parser.add_argument("--file", default="issues_data.json", help="Path to issues JSON file")
    args = parser.parse_args()
    main(file_path=args.file)
