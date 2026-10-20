# -*- coding: utf-8 -*-
r"""把 网页版\ 推到 GitHub（HTTPS + Token，因为这台机器连不上 GitHub 的 SSH 端口）。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


def run(cmd, check=True):
    p = subprocess.run(cmd, shell=True)
    if check and p.returncode != 0:
        sys.exit(1)
    return p.returncode


def main():
    print()
    print("  这一步要两样东西：你的 GitHub 用户名、一个 Personal Access Token。")
    print()
    print("  没有 Token？浏览器打开：")
    print("    https://github.com/settings/tokens/new")
    print("    Note 随便写（hotrod），Expiration 选 30 days，")
    print("    Scope 只勾第一个「repo」，拉到最底点 Generate token，")
    print("    生成的 ghp_ 开头那一串只显示一次，复制下来。")
    print()
    user = input("  GitHub 用户名: ").strip()
    if not user:
        print("  没输入，退出。")
        return
    repo = input("  仓库名（直接回车 = hotrod）: ").strip() or "hotrod"
    token = input("  粘贴 Token（输入时不显示是正常的，粘完回车）: ").strip()
    if not token:
        print("  没输入 Token，退出。")
        return

    url = "https://github.com/%s/%s.git" % (user, repo)
    auth = "https://%s:%s@github.com/%s/%s.git" % (user, token, user, repo)

    run("git remote remove origin >nul 2>nul || exit 0")
    run("git remote add origin %s" % url)

    print()
    print("  正在推送……")
    rc = run('git -c credential.helper= push "%s" main:main -u' % auth, check=False)
    if rc != 0:
        print()
        print("  推送失败。常见原因：")
        print("    - 仓库还没建：先去 https://github.com/new 建一个 public 的 %s" % repo)
        print("    - Token 复制不全 / 过期：重新生成（要勾 repo）")
        print("    - 用户名写错：是用户名，不是邮箱")
        print()
        input("  按回车关闭…")
        return

    print()
    print("  推送完成。最后一步（只有你能在网页上点）：")
    print("    1. 打开 https://github.com/%s/%s/settings/pages" % (user, repo))
    print("    2. Source 选 Deploy from a branch")
    print("    3. Branch 选 main、目录选 / (root)，点 Save")
    print("    4. 等 1~2 分钟，网址就是：")
    print()
    print("       https://%s.github.io/%s/" % (user, repo))
    print()
    print("  以后改了游戏：把新的 热棒撸罐.html 复制成 网页版\\index.html，再跑一次本脚本。")
    print()
    input("  按回车关闭…")


if __name__ == "__main__":
    main()
