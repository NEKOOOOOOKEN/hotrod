# -*- coding: utf-8 -*-
r"""本机小代理：把 github.com 指到一个能连通的 IP。

背景：这台机器的 DNS 把 github.com 解析到 20.205.243.166，而那个 IP 的 443
端口根本连不上（api.github.com 却是通的）。改 hosts 需要管理员权限，所以退而
求其次：起一个本地 HTTP CONNECT 隧道代理，git 走 -c http.proxy= 指过来即可。

用法（另开一个窗口，保持运行）：
    python git代理.py            # 默认 127.0.0.1:18080

然后：
    git -c http.proxy=http://127.0.0.1:18080 push origin main
    git -c http.proxy=http://127.0.0.1:18080 fetch

也可以给普通命令用：
    curl -x http://127.0.0.1:18080 https://github.com/
"""
import argparse
import select
import socket
import socketserver
import sys
import threading

# 会被改写目标的域名 -> 候选 IP（实测能连通的那几个，轮着用；
# 本机 DNS 给的 20.205.243.166 在 443 上连不通，而且单个 IP 用几次就会被掐）
PINNED = {
    "github.com": [
        "140.82.112.3",
        "140.82.113.3",
        "20.27.177.113",
        "140.82.114.3",
        "4.237.22.38",
        "20.233.83.145",
        "140.82.116.3",
    ],
}
_PICK = {}


def resolve(host):
    ips = PINNED.get(host.lower())
    if not ips:
        return [socket.gethostbyname(host)]
    n = _PICK.get(host.lower(), 0)
    _PICK[host.lower()] = n + 1
    return ips[n % len(ips):] + ips[:n % len(ips)]


def connect_any(host, port):
    last = None
    for ip in resolve(host):
        try:
            return socket.create_connection((ip, port), timeout=6), ip
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or OSError("no ip")


class Tunnel(socketserver.BaseRequestHandler):
    def handle(self):
        cli = self.request
        try:
            cli.settimeout(30)
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = cli.recv(4096)
                if not chunk:
                    return
                head += chunk
                if len(head) > 65536:
                    return
            hdr, _, rest = head.partition(b"\r\n\r\n")
            line = hdr.split(b"\r\n", 1)[0].decode("latin-1")
            parts = line.split()
            if len(parts) < 2:
                cli.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            method, target = parts[0], parts[1]
            if method.upper() != "CONNECT":
                cli.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return
            host, _, port = target.rpartition(":")
            port = int(port or 443)
            upstream, ip = connect_any(host, port)
            print("  %s:%d -> %s" % (host, port, ip), flush=True)
        except Exception as e:  # noqa: BLE001
            print("  ! 连接失败:", e, file=sys.stderr, flush=True)
            try:
                cli.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except Exception:
                pass
            return

        try:
            cli.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            if rest:  # 头部之后可能已经带着请求体（POST），别丢了
                upstream.sendall(rest)
            cli.settimeout(None)
            upstream.settimeout(None)
            self.pump(cli, upstream)
        finally:
            for s in (cli, upstream):
                try:
                    s.close()
                except Exception:
                    pass

    @staticmethod
    def pump(a, b):
        socks = [a, b]
        while True:
            try:
                r, _, x = select.select(socks, [], socks, 120)
            except Exception:
                return
            if x or not r:
                return
            for s in r:
                try:
                    data = s.recv(65536)
                except Exception:
                    return
                if not data:
                    return
                other = b if s is a else a
                try:
                    other.sendall(data)
                except Exception:
                    return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18080)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = Server((args.host, args.port), Tunnel)
    print("github 代理已启动: %s:%d" % (args.host, args.port))
    print("git -c http.proxy=http://%s:%d push origin main" % (args.host, args.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("已停止")


if __name__ == "__main__":
    threading.stack_size(256 * 1024)
    main()
