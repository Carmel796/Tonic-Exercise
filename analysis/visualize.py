#!/usr/bin/env python3
import json
import argparse
import matplotlib.pyplot as plt
from pathlib import Path

def read_jsonl_counts(path: Path) -> dict:
    data = {}
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if "server" in item:
                data[item["server"]] = item["count"]
            elif "technology" in item:
                data[item["technology"]] = item["count"]
    return data

def main(top_n: int = 15):
    OUTPUT_DIR = Path(__file__).parent / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

    SERVER_PNG = OUTPUT_DIR / "server_counts.png"
    TECH_PNG   = OUTPUT_DIR / "technology_counts.png"

    # load
    server_counts = read_jsonl_counts(OUTPUT_DIR / "server_counts.jsonl")
    tech_counts   = read_jsonl_counts(OUTPUT_DIR / "technology_counts.jsonl")

    # sort
    top_servers = dict(sorted(server_counts.items(), key=lambda x: x[1], reverse=True)[:top_n])
    tech_counts_sorted = dict(sorted(tech_counts.items(), key=lambda x: x[1], reverse=True))

    # server bar chart
    plt.figure(figsize=(10, 6))
    plt.barh(list(top_servers.keys())[::-1], list(top_servers.values())[::-1])
    plt.title(f"Top {top_n} Servers by Frequency")
    plt.xlabel("Occurrences")
    plt.ylabel("Server Name")
    plt.tight_layout()
    plt.savefig(SERVER_PNG, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Saved: {SERVER_PNG.name}")

    # tech bar chart
    plt.figure(figsize=(8, 6))
    plt.bar(list(tech_counts_sorted.keys()), list(tech_counts_sorted.values()))
    plt.title("Technology Classification Distribution")
    plt.xlabel("Technology Type")
    plt.ylabel("Count")
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(TECH_PNG, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Saved: {TECH_PNG.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create bar charts from JSONL counts.")
    parser.add_argument("--top-n", type=int, default=15, help="How many top servers to plot")
    args = parser.parse_args()
    main(top_n=args.top_n)
