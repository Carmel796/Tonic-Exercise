import os, json, requests, time
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from generate_issues import generate_description

load_dotenv()

JIRA_BASE_URL  = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL     = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY    = os.getenv("JIRA_PROJECT_KEY")

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Content-Type": "application/json"}

def adf_from_text(text: str) -> dict:
    """
    Minimal ADF: split on blank lines => paragraphs,
    single newlines => hardBreaks inside a paragraph.
    """
    doc = {"type": "doc", "version": 1, "content": []}
    for para in text.split("\n\n"):
        nodes = []
        lines = para.split("\n")
        for i, line in enumerate(lines):
            if line:
                nodes.append({"type": "text", "text": line})
            if i < len(lines) - 1:
                nodes.append({"type": "hardBreak"})
        # ensure empty paragraphs still render
        if not nodes:
            nodes = [{"type": "text", "text": ""}]
        doc["content"].append({"type": "paragraph", "content": nodes})
    if not doc["content"]:
        doc["content"] = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]
    return doc

def create_bulk_issues(total=20000, batch_size=50):
    created = 0
    while created < total:
        issues = []
        for i in range(batch_size):
            tech, desc = generate_description()
            issues.append({
                "fields": {
                    "project": {"key": PROJECT_KEY},
                    "issuetype": {"name": "Task"},
                    "summary": f"Ticket {created + i + 1}",
                    "description": adf_from_text(desc)
                }
            })

        url = f"{JIRA_BASE_URL}/rest/api/3/issue/bulk"
        r = requests.post(url, headers=headers, auth=auth, json={"issueUpdates": issues})

        if r.status_code == 201:
            data = r.json()
            count = len(data.get("issues", []))
            created += count
            print(f"✅ Created {created}/{total} issues")
        else:
            print(f"❌ Failed batch ({r.status_code})")
            try:
                print(r.json())
            except Exception:
                print(r.text)
            # simple pause; you can remove or tweak
            time.sleep(2)
            # optional: break if it's a validation error you want to inspect
            break

def main():
    create_bulk_issues()

if __name__ == "__main__":
    main()
