# -*- coding: utf-8 -*-
"""地平线6 调校速查 · 局域网访问服务（兜底方案）

手机与电脑连同一个 WiFi，用手机浏览器打开脚本打印的地址即可访问。
不依赖公网、不依赖发布服务，关掉窗口即停止。

用法：python scripts/serve.py [端口]
"""
import http.server
import os
import socket
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(BASE), "docs")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE, **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("223.5.5.5", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def main():
    if not os.path.exists(os.path.join(SITE, "index.html")):
        print("!! 没找到 docs/index.html，请先运行 update.py 生成页面。")
        return 1

    ip = lan_ip()
    print("=" * 46)
    print("  地平线6 调校速查 - 手机访问")
    print("=" * 46)
    print()
    print("  让手机连上与本电脑同一个 WiFi，")
    print("  然后用手机浏览器打开：")
    print()
    if ip:
        print("        http://%s:%d" % (ip, PORT))
    else:
        print("        http://<本机局域网IP>:%d" % PORT)
    print()
    print("  本机自测：http://127.0.0.1:%d" % PORT)
    print()
    print("  保持这个窗口开着；关闭窗口即停止服务。")
    print("=" * 46)
    print()
    sys.stdout.flush()

    try:
        httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError as e:
        print("!! 端口 %d 起不来：%s" % (PORT, e))
        print("   端口可能被占用，换个端口重试，例如：")
        print("   python scripts\\serve.py 8090")
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
