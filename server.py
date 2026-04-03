"""藏经阁 HTTP 服务器"""
import asyncio
import gzip
import hashlib
import json
import mimetypes
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from crawler import crawl_book
from watermark import clean_chapters

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"
BOOKS_FILE = DATA_DIR / "books.json"

# --- 全局状态 ---
_chapter_cache: dict[str, tuple[bytes, str]] = {}  # id -> (gzip_bytes, etag)
_progress: dict[str, dict] = {}  # book_id -> {chapter, ts}
_progress_dirty = False
_sse_clients: list = []  # [(wfile, lock)]
_crawl_status: dict = {}  # {book_id, status, done, total, fail, error}
_lock = threading.Lock()


# --- 数据读写 ---
def _load_books() -> list[dict]:
    if BOOKS_FILE.exists():
        return json.loads(BOOKS_FILE.read_text("utf-8"))
    return []


def _save_books(books: list[dict]):
    BOOKS_FILE.write_text(json.dumps(books, ensure_ascii=False, indent=2), "utf-8")


def _chapters_path(book_id: str) -> Path:
    return DATA_DIR / "books" / book_id / "chapters.json"


def _progress_path(book_id: str) -> Path:
    return DATA_DIR / "books" / book_id / "progress.json"


def _load_progress(book_id: str) -> dict | None:
    p = _progress_path(book_id)
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    return None


def _save_progress_file(book_id: str, data: dict):
    p = _progress_path(book_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), "utf-8")


def _init_progress():
    """启动时从磁盘加载所有进度到内存"""
    books_dir = DATA_DIR / "books"
    if not books_dir.exists():
        return
    for d in books_dir.iterdir():
        if d.is_dir():
            prog = _load_progress(d.name)
            if prog:
                _progress[d.name] = prog


_chapters_parsed: dict[str, list] = {}  # book_id -> parsed chapters list

def _get_chapters_parsed(book_id: str) -> list | None:
    """返回解析后的章节列表，带缓存"""
    if book_id in _chapters_parsed:
        return _chapters_parsed[book_id]
    cp = _chapters_path(book_id)
    if not cp.exists():
        return None
    chapters = json.loads(cp.read_text("utf-8"))
    _chapters_parsed[book_id] = chapters
    return chapters

def _get_chapters_gz(book_id: str) -> tuple[bytes, str] | None:
    """返回 (gzip_bytes, etag)，带缓存"""
    if book_id in _chapter_cache:
        return _chapter_cache[book_id]
    cp = _chapters_path(book_id)
    if not cp.exists():
        return None
    raw = cp.read_bytes()
    gz = gzip.compress(raw, compresslevel=6)
    etag = hashlib.md5(raw).hexdigest()
    _chapter_cache[book_id] = (gz, etag)
    return gz, etag


def _invalidate_cache(book_id: str):
    _chapter_cache.pop(book_id, None)
    _chapters_parsed.pop(book_id, None)


# --- SSE ---
def _sse_broadcast(book_id: str, data: dict):
    msg = f"data: {json.dumps({'book_id': book_id, **data}, ensure_ascii=False)}\n\n"
    dead = []
    for i, (wfile, lock) in enumerate(_sse_clients):
        try:
            with lock:
                wfile.write(msg.encode())
                wfile.flush()
        except Exception:
            dead.append(i)
    for i in reversed(dead):
        _sse_clients.pop(i)


# --- 后台刷盘线程 ---
def _flush_loop():
    global _progress_dirty
    while True:
        time.sleep(3)
        with _lock:
            if not _progress_dirty:
                continue
            _progress_dirty = False
            snapshot = dict(_progress)
        for bid, data in snapshot.items():
            _save_progress_file(bid, data)


# --- 爬虫后台 ---
def _crawl_in_bg(book: dict, api_url: str | None):
    bid = book["id"]
    _crawl_status.update(book_id=bid, status="crawling", done=0,
                         total=book["chapter_count"], fail=0, error=None)

    def on_progress(done, fail, total):
        _crawl_status.update(done=done, fail=fail, total=total)

    loop = asyncio.new_event_loop()
    try:
        chapters, _prog = loop.run_until_complete(crawl_book(
            book["book_id"], book["chapter_start"], book["chapter_end"],
            book_name=book["name"], api_url=api_url or None,
            on_progress=on_progress,
        ))
        out_dir = DATA_DIR / "books" / bid
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "chapters.json").write_text(
            json.dumps(chapters, ensure_ascii=False), "utf-8")
        book["chapter_count"] = len(chapters)
        books = _load_books()
        for b in books:
            if b["id"] == bid:
                b["chapter_count"] = len(chapters)
                break
        _save_books(books)
        _invalidate_cache(bid)
        _crawl_status.update(status="done", done=len(chapters))
        print(f"[爬虫] {book['name']} 完成, 共{len(chapters)}章")
    except Exception as e:
        _crawl_status.update(status="error", error=str(e))
        print(f"[爬虫] {book['name']} 失败: {e}")
    finally:
        loop.close()


# --- HTTP Handler ---
class Handler(BaseHTTPRequestHandler):
    server_version = "CangJingGe/1.0"

    def log_message(self, fmt, *args):
        pass  # 静默日志

    def _json_resp(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def _serve_file(self, filepath: Path):
        if not filepath.exists() or not filepath.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(filepath))
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", len(data))
        self.send_header("Access-Control-Allow-Origin", "*")
        if str(filepath).endswith(".html"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    # --- GET ---
    def do_GET(self):
        path = urlparse(self.path).path

        # 首页
        if path == "/":
            return self._serve_file(WEB_DIR / "index.html")

        # 阅读页
        m = re.match(r"^/read/([^/]+)$", path)
        if m:
            return self._serve_file(WEB_DIR / "reader.html")

        # API: 书籍列表
        if path == "/api/books":
            books = _load_books()
            for b in books:
                prog = _progress.get(b["id"])
                b["progress"] = prog if prog else None
            return self._json_resp(books)

        # API: 章节元数据（仅标题，快速加载）
        m = re.match(r"^/api/books/([^/]+)/chapters/meta$", path)
        if m:
            bid = m.group(1)
            chapters = _get_chapters_parsed(bid)
            if chapters is None:
                return self.send_error(404)
            meta = [{"index": i, "id": ch.get("id", i+1), "title": ch["title"]} for i, ch in enumerate(chapters)]
            return self._json_resp(meta)

        # API: 章节列表 (Gzip + ETag)
        m = re.match(r"^/api/books/([^/]+)/chapters$", path)
        if m:
            bid = m.group(1)
            all_chapters = _get_chapters_parsed(bid)
            if all_chapters is None:
                return self.send_error(404)

            # 解析查询参数
            from urllib.parse import parse_qs
            query = parse_qs(urlparse(self.path).query)
            start = int(query.get('start', [0])[0])
            limit = int(query.get('limit', [-1])[0])

            # 切片处理
            if limit > 0:
                chapters = all_chapters[start:start + limit]
            else:
                chapters = all_chapters

            # 压缩并返回（根据Accept-Encoding决定是否压缩）
            raw = json.dumps(chapters, ensure_ascii=False).encode()
            etag = hashlib.md5(raw).hexdigest()

            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.end_headers()
                return

            # 检查客户端是否支持gzip
            accept_encoding = self.headers.get("Accept-Encoding", "")
            use_gzip = "gzip" in accept_encoding.lower()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Access-Control-Allow-Origin", "*")

            if use_gzip:
                gz = gzip.compress(raw, compresslevel=6)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", len(gz))
                self.end_headers()
                self.wfile.write(gz)
            else:
                self.send_header("Content-Length", len(raw))
                self.end_headers()
                self.wfile.write(raw)
            return

        # API: 阅读进度
        m = re.match(r"^/api/books/([^/]+)/progress$", path)
        if m:
            bid = m.group(1)
            prog = _progress.get(bid) or _load_progress(bid) or {}
            return self._json_resp(prog)

        # API: 爬虫状态
        if path == "/api/crawl/status":
            return self._json_resp(_crawl_status)

        # SSE: 进度同步流
        if path == "/api/progress/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            lock = threading.Lock()
            _sse_clients.append((self.wfile, lock))
            # 发送心跳保持连接
            try:
                while True:
                    time.sleep(30)
                    with lock:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            return

        # favicon.ico
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 静态文件: /sw.js, /manifest.json, /icons/*, /web/*
        if path == "/sw.js":
            return self._serve_file(BASE_DIR / "web" / "sw.js")
        if path == "/manifest.json":
            return self._serve_file(BASE_DIR / "web" / "manifest.json")
        if path.startswith("/icons/"):
            return self._serve_file(BASE_DIR / path.lstrip("/"))
        if path.startswith("/web/"):
            return self._serve_file(BASE_DIR / path.lstrip("/"))

        self.send_error(404)

    # --- OPTIONS ---
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # --- POST ---
    def do_POST(self):
        global _progress_dirty
        path = urlparse(self.path).path

        # 保存进度
        m = re.match(r"^/api/books/([^/]+)/progress$", path)
        if m:
            bid = m.group(1)
            body = self._read_body()
            new_chapter = body.get("chapter", -1)
            new_ts = body.get("ts", 0)
            with _lock:
                cur = _progress.get(bid, {})
                cur_chapter = cur.get("chapter", -1)
                cur_ts = cur.get("ts", 0)
                # 章节数优先，章节相同时比较时间戳
                if cur_chapter > new_chapter:
                    return self._json_resp({"ok": False, "msg": "进度较旧"}, 409)
                if cur_chapter == new_chapter and cur_ts >= new_ts:
                    return self._json_resp({"ok": False, "msg": "时间戳过旧"}, 409)
                _progress[bid] = body
                _progress_dirty = True
            _sse_broadcast(bid, body)
            return self._json_resp({"ok": True})

        # 添加书籍并爬取
        if path == "/api/books/add":
            body = self._read_body()
            name = body.get("name", "").strip()
            book_id = str(body.get("book_id", "")).strip()
            cs = int(body.get("chapter_start", 0))
            ce = int(body.get("chapter_end", 0))
            api_url = body.get("api_url")
            if not name or not book_id or ce < cs:
                return self._json_resp({"ok": False, "msg": "参数错误"}, 400)
            bid = hashlib.md5(f"{book_id}_{cs}_{ce}".encode()).hexdigest()[:12]
            book = {
                "id": bid, "name": name, "author": body.get("author", ""),
                "source": body.get("source", ""), "book_id": book_id,
                "chapter_count": ce - cs + 1,
                "chapter_start": cs, "chapter_end": ce,
            }
            books = _load_books()
            books.append(book)
            _save_books(books)
            threading.Thread(target=_crawl_in_bg, args=(book, api_url),
                             daemon=True).start()
            return self._json_resp({"ok": True, "id": bid})

        # 清除水印
        m = re.match(r"^/api/books/([^/]+)/clean$", path)
        if m:
            bid = m.group(1)
            cp = _chapters_path(bid)
            if not cp.exists():
                return self._json_resp({"ok": False, "msg": "章节不存在"}, 404)
            body = self._read_body()
            custom_watermarks = body.get("watermarks", []) if body else []
            chapters = json.loads(cp.read_text("utf-8"))
            chapters, removed = clean_chapters(chapters, custom_watermarks=custom_watermarks)
            cp.write_text(json.dumps(chapters, ensure_ascii=False), "utf-8")
            _invalidate_cache(bid)
            return self._json_resp({"ok": True, "removed": removed})

        self.send_error(404)


# --- 启动 ---
def _get_lan_ips() -> list[str]:
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return list(set(ips)) or ["127.0.0.1"]


def start_server(port=8080):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "books").mkdir(exist_ok=True)
    _init_progress()

    # 启动刷盘线程
    threading.Thread(target=_flush_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[藏经阁] 服务启动 端口 {port}")
    for ip in _get_lan_ips():
        print(f"  http://{ip}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[藏经阁] 服务已停止")
        server.server_close()


if __name__ == "__main__":
    import sys
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_server(p)
