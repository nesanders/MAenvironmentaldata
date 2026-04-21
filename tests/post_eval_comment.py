"""Post eval summary.json as a PR comment via the GitHub API.

Usage (called from GHA workflow):
  python tests/post_eval_comment.py

Environment variables required:
  GITHUB_TOKEN       - GitHub Actions token with pull-requests:write permission
  GITHUB_REPOSITORY  - e.g. "nesanders/MAenvironmentaldata"
  PR_NUMBER          - pull request number (set in workflow from github.event.number)
"""
import json
import os
import sys
import urllib.request
import urllib.error

SUMMARY_PATH = os.path.join(os.path.dirname(__file__), "eval_results", "summary.json")


def format_comment(summary_data):
    s = summary_data["summary"]
    hard_rate = s.get("hard_pass_rate", 0)
    status_icon = "✅" if s["fatal_failures"] == 0 and hard_rate >= 0.80 else "❌"

    lines = [
        f"## {status_icon} Semantic Eval Results",
        "",
        "Each eval sends a natural-language question plus the relevant table schemas from "
        "`db_semantic_context.txt` to `gpt-4o-mini`, executes the generated SQL against "
        "`AMEND.db`, then scores it with a second LLM call using a per-case rubric. "
        "Hard pass = SQL ran and returned rows without hitting any known anti-patterns. "
        "Fatal = judge determined the query would return wrong or misleading results.",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Hard pass rate | {s['hard_pass']}/{s['total']} ({hard_rate:.0%}) |",
        f"| Fatal failures | {s['fatal_failures']} |",
        f"| Mean judge score | {s.get('mean_judge_score', 'n/a')}/5 |",
        f"| P50 judge score | {s.get('p50_judge_score', 'n/a')}/5 |",
        f"| Model | {summary_data.get('model', 'unknown')} |",
        f"| Semantic context hash | `{summary_data.get('semantic_context_hash', 'n/a')}` |",
        "",
        "<details><summary>Per-case results</summary>",
        "",
        "| ID | Hard pass | Score | Fatal | Reason |",
        "|----|-----------|-------|-------|--------|",
    ]

    for r in summary_data.get("results", []):
        hard = "✅" if r["passed_hard"] else "❌"
        fatal = "⚠️ YES" if r["judge_fatal"] else "no"
        reason = (r["judge_reason"] or "").replace("|", "\\|")
        lines.append(f"| `{r['id']}` | {hard} | {r['judge_score']}/5 | {fatal} | {reason} |")

    lines += ["", "</details>"]
    return "\n".join(lines)


def post_comment(body):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")

    if not all([token, repo, pr_number]):
        print("Missing GITHUB_TOKEN, GITHUB_REPOSITORY, or PR_NUMBER — skipping comment")
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    payload = json.dumps({"body": body}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Posted PR comment (status {resp.status})")
    except urllib.error.HTTPError as e:
        print(f"Failed to post PR comment: {e.code} {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    if not os.path.exists(SUMMARY_PATH):
        print(f"summary.json not found at {SUMMARY_PATH} — nothing to post")
        sys.exit(0)

    with open(SUMMARY_PATH) as f:
        data = json.load(f)

    body = format_comment(data)
    print(body)
    post_comment(body)
