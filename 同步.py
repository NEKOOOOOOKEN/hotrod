# -*- coding: utf-8 -*-
r"""一条命令把成品同步到 GitHub（自动复制、提交、推送，必要时自己起代理）。

用法：
    python 同步.py                 # 用 热棒撸罐.html 覆盖 网页版\index.html 再推
    python 同步.py 提交信息         # 自定义提交信息
    python 同步.py --no-push       # 只复制 + 提交，不推

需要的东西（只配一次）：
    把 GitHub 的 Personal Access Token（ghp_ 开头，勾 repo）写进同目录的 .token
    这个文件已经在 .gitignore 里，不会被提交。
"""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # 网页版\
ROOT = HERE.parent                              # 热棒撸罐\
USER = "NEKOOOOOOKEN"
REPO = "hotrod"
TOKEN_FILE = HERE / ".token"
PROXY = HERE / "git代理.py"
PROXY_ADDR = "127.0.0.1:18080"
GIT = ["git", "-c", "user.name=hotrod", "-c", "user.email=hotrod@users.noreply.github.com"]


def say(msg):
    print("  " + msg, flush=True)


def run(cmd, timeout=180, env=None, quiet=False):
    p = subprocess.run(cmd, cwd=str(HERE), timeout=timeout,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, env=env)
    out = p.stdout.decode("utf-8", "replace").strip()
    if not quiet and out:
        print(out)
    return p.returncode, out


def port_open(addr):
    host, port = addr.split(":")
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex((host, int(port))) == 0


def ensure_proxy():
    if port_open(PROXY_ADDR):
        return True
    if not PROXY.exists():
        return False
    say("github.com 直连不通，起本地代理 %s …" % PROXY_ADDR)
    subprocess.Popen([sys.executable, str(PROXY)], cwd=str(HERE),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(25):
        time.sleep(0.4)
        if port_open(PROXY_ADDR):
            say("代理已就绪")
            return True
    return False


def main():
    args = [a for a in sys.argv[1:]]
    no_push = "--no-push" in args
    args = [a for a in args if a != "--no-push"]

    # 1) 复制成品
    src = ROOT / "热棒撸罐.html"
    dst = HERE / "index.html"
    if not src.exists():
        say("找不到 %s，先跑 构建.py" % src)
        return 1
    shutil.copyfile(src, dst)
    say("已复制 %s → index.html（%s 字节）" % (src.name, format(dst.stat().st_size, ",")))

    # 2) 提交
    msg = args[0] if args else "同步构建 " + time.strftime("%Y-%m-%d %H:%M")
    run(GIT + ["add", "-A"], quiet=True)
    code, out = run(GIT + ["commit", "-m", msg], quiet=True)
    if code == 0:
        say("已提交：" + msg)
    elif "nothing to commit" in out:
        say("没有新改动，跳过提交")
    else:
        print(out)

    if no_push:
        return 0

    # 3) 推送（token 从 .token 读）
    if not TOKEN_FILE.exists():
        say("缺 %s ——把 GitHub Token（ghp_ 开头、勾 repo）粘进去，只粘一行。" % TOKEN_FILE.name)
        say("浏览器：https://github.com/settings/tokens/new")
        say("提交已经在本地了，配好 token 再跑一次 同步.py 就能推。")
        return 2
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        say("%s 是空的" % TOKEN_FILE.name)
        return 2

    url = "https://%s:%s@github.com/%s/%s.git" % (USER, token, USER, REPO)
    base = GIT + ["-c", "credential.helper=", "-c", "http.postBuffer=524288000"]

    say("推送 main → %s/%s …" % (USER, REPO))
    code, out = run(base + ["push", url, "main:main"], timeout=300)
    if code != 0:
        if ensure_proxy():
            code, out = run(base + ["-c", "http.proxy=http://" + PROXY_ADDR,
                                    "push", url, "main:main"], timeout=300)
    if code != 0:
        # git push 走 github.com:443，这台机器这条路经常不通 → 改走 api.github.com
        say("git push 不通，改走 GitHub API 推送…")
        code2, _ = run([sys.executable, str(HERE / "api推送.py"), msg], timeout=600)
        if code2 != 0:
            say("API 推送也失败了，看上面的输出")
            return 1
        return 0

    say("推送成功。等 1~2 分钟 Pages 重建，然后打开：")
    say("https://nekooooooken.github.io/hotrod/?v=%d" % int(time.time()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
