# -*- coding: utf-8 -*-
r"""通过 GitHub 的 Git Data API 把本地提交推上去。

为什么不用 git push：这台机器上 github.com:443 走不通（DNS 指到一个死 IP），
但 api.github.com 是通的。所以这里用 API 传 blob / 建 tree / 建 commit / 挪 ref，
效果和 git push 一样，网站会自动重建。

用法：
    python api推送.py            # 提交信息自动生成
    python api推送.py "说明"
需要同目录的 .token（ghp_ 开头，勾 repo）。
"""
import base64
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER = "NEKOOOOOOKEN"
REPO = "hotrod"
BRANCH = "main"
API = "https://api.github.com"
TOKEN_FILE = HERE / ".token"


def token():
    t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not t:
        sys.exit("  .token 是空的")
    return t


def api(method, path, body=None, tok=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + (tok or token()))
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "hotrod-sync")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        sys.exit("  API %s %s 失败：%s %s" % (method, path, e.code, detail))


def git(*args):
    p = subprocess.run(["git"] + list(args), cwd=str(HERE),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        sys.exit("  git %s 失败：%s" % (" ".join(args), p.stdout.decode("utf-8", "replace")[:400]))
    return p.stdout.decode("utf-8", "replace")


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "同步构建 " + time.strftime("%Y-%m-%d %H:%M")

    ref = api("GET", "/repos/%s/%s/git/ref/heads/%s" % (USER, REPO, BRANCH))
    base_commit = ref["object"]["sha"]
    commit = api("GET", "/repos/%s/%s/git/commits/%s" % (USER, REPO, base_commit))
    base_tree = commit["tree"]["sha"]
    flat = api("GET", "/repos/%s/%s/git/trees/%s?recursive=1" % (USER, REPO, base_tree))
    remote = {e["path"]: e["sha"] for e in flat.get("tree", []) if e["type"] == "blob"}
    print("  远端 main = %s（%d 个文件）" % (base_commit[:7], len(remote)))

    # 本地工作区里被 git 跟踪的文件
    entries = []
    for line in git("-c", "core.quotepath=false", "ls-files", "-s").strip().splitlines():
        meta, path = line.split("\t", 1)
        mode, sha, _ = meta.split()
        if mode not in ("100644", "100755"):
            continue
        entries.append((path, mode, sha))

    changed = []
    tree_items = []
    for path, mode, sha in entries:
        if remote.get(path) == sha:
            continue
        raw = (HERE / path).read_bytes()
        blob = api("POST", "/repos/%s/%s/git/blobs" % (USER, REPO),
                   {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
        tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        changed.append("%s (%.1f KB)" % (path, len(raw) / 1024))
        print("  上传 " + changed[-1])

    if not tree_items:
        print("  远端已经是最新，什么都不用传")
        return 0

    tree = api("POST", "/repos/%s/%s/git/trees" % (USER, REPO),
               {"base_tree": base_tree, "tree": tree_items})
    newc = api("POST", "/repos/%s/%s/git/commits" % (USER, REPO),
               {"message": msg, "tree": tree["sha"], "parents": [base_commit]})
    api("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (USER, REPO, BRANCH),
        {"sha": newc["sha"], "force": False})
    print("  提交成功：%s（%s）" % (newc["sha"][:7], msg))

    # 记下远端位置（本地没有这个对象，update-ref 会失败，忽略即可）
    (HERE / ".远端HEAD").write_text(newc["sha"], encoding="utf-8")
    print("  等 1~2 分钟 Pages 重建，然后打开：")
    print("  https://nekooooooken.github.io/hotrod/?v=%d" % int(time.time()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
