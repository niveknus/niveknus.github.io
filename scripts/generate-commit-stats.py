#!/usr/bin/env python3
"""
Generate commit-data.json for the GitHub Pages activity visualizations.
Queries all niveknus repos via the GitHub API, collects every commit
timestamp, and writes a compact JSON file consumed by projects/index.html.

Requires GH_TOKEN env var with repo scope (for private repos).
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

OWNER = "niveknus"
REPOS = ["second-brain", "niveknus.github.io", "second-brain-shared"]
SINCE = "2026-04-28T00:00:00Z"  # project start date
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "")


def gh_get(url):
    """Make an authenticated GET request to the GitHub API."""
    req = Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urlopen(req) as resp:
        # Parse Link header for pagination
        link_header = resp.headers.get("Link", "")
        next_url = None
        if link_header:
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split("<")[1].split(">")[0]
        data = json.loads(resp.read().decode())
        return data, next_url


def get_all_commits(repo):
    """Paginate through all commits for a repo since SINCE date."""
    commits = []
    url = f"{API}/repos/{OWNER}/{repo}/commits?since={SINCE}&per_page=100"

    while url:
        try:
            data, next_url = gh_get(url)
        except HTTPError as e:
            print(f"  Warning: HTTP {e.code} for {repo} — skipping", file=sys.stderr)
            break

        for c in data:
            # Use author date (when the code was written), fall back to committer date
            date_str = (
                c.get("commit", {}).get("author", {}).get("date")
                or c.get("commit", {}).get("committer", {}).get("date")
            )
            if date_str:
                commits.append(date_str)

        url = next_url
        if data:
            print(f"  {repo}: fetched {len(commits)} commits so far...", file=sys.stderr)

    return commits


def main():
    all_commits = []  # list of [timestamp, repo_name]
    by_repo = {}

    for repo in REPOS:
        print(f"Fetching {repo}...", file=sys.stderr)
        timestamps = get_all_commits(repo)
        by_repo[repo] = len(timestamps)
        for ts in timestamps:
            all_commits.append([ts, repo])
        print(f"  {repo}: {len(timestamps)} total commits", file=sys.stderr)

    # Sort by timestamp ascending
    all_commits.sort(key=lambda x: x[0])

    total = sum(by_repo.values())
    print(f"\nTotal: {total} commits across {len(REPOS)} repos", file=sys.stderr)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": SINCE,
        "total": total,
        "by_repo": by_repo,
        "commits": all_commits,  # [[timestamp, repo], ...]
    }

    # Write to commit-data.json at repo root
    out_path = os.path.join(os.path.dirname(__file__), "..", "commit-data.json")
    out_path = os.path.normpath(out_path)
    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))  # compact

    print(f"Wrote {out_path} ({os.path.getsize(out_path)} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
