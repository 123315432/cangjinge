"""藏经阁 - 小说阅读器"""
import sys
import threading
import webview

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    # 在后台线程启动 HTTP 服务器
    from server import start_server
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # 快速等待服务器就绪
    import time
    import socket
    for _ in range(20):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            sock.connect(('localhost', port))
            sock.close()
            break
        except Exception:
            time.sleep(0.05)

    # 创建原生窗口
    window = webview.create_window(
        '藏经阁',
        f'http://localhost:{port}',
        width=1100,
        height=800,
        min_size=(400, 500),
    )
    webview.start()

if __name__ == '__main__':
    main()
