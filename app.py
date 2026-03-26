"""藏经阁 - 小说阅读器"""
import sys
import json
import threading
import webview
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

def get_last_book():
    """找到最近阅读的书"""
    books_dir = DATA_DIR / "books"
    latest = None
    latest_ts = 0
    for prog_file in books_dir.glob("*/progress.json"):
        try:
            prog = json.loads(prog_file.read_text("utf-8"))
            ts = prog.get("ts", 0)
            if ts > latest_ts:
                latest_ts = ts
                latest = prog_file.parent.name
        except Exception:
            pass
    return latest

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    from server import start_server
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

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

    # 直接跳到上次阅读的书
    last_book = get_last_book()
    if last_book:
        url = f'http://localhost:{port}/read/{last_book}'
    else:
        url = f'http://localhost:{port}'

    storage_dir = str(DATA_DIR / "webview_storage")

    window = webview.create_window(
        '藏经阁',
        url,
        width=1100,
        height=800,
        min_size=(400, 500),
    )
    webview.start(private_mode=False, storage_path=storage_dir)

if __name__ == '__main__':
    main()
