"""藏经阁 - 小说阅读器"""
import sys
import threading
import webview

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    # 在后台线程启动 HTTP 服务器
    from server import start_server
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # 等服务器就绪
    import time
    import urllib.request
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/api/books', timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    # 创建原生窗口
    window = webview.create_window(
        '藏经阁',
        f'http://localhost:{port}',
        width=1100,
        height=800,
        min_size=(400, 500),
    )
    webview.start(debug=True)

if __name__ == '__main__':
    main()
