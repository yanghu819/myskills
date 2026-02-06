import base64
import json
import os
import urllib.error
import urllib.request

token = os.environ["GITHUB_TOKEN"]
owner = os.environ.get("MYSKILLS_OWNER", "yanghu819")
repo = os.environ.get("MYSKILLS_REPO", "myskills")
paths = os.environ.get(
    "MYSKILLS_PATHS",
    "mac-cloud-smoke/SKILL.md mac-cloud-smoke/autodl.sh github-backup-myskills/SKILL.md github-backup-myskills/backup.py",
).split()

for path in paths:
    with open(path, "rb") as f:
        content = f.read()

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    sha = None
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req) as resp:
            cur = json.load(resp)
        sha = cur.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    payload = {
        "message": f"backup myskills: {path}",
        "content": base64.b64encode(content).decode("ascii"),
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(url, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, data=json.dumps(payload).encode("utf-8")) as resp:
        out = json.load(resp)

    print(path, out["commit"]["sha"])
