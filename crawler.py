"""爬虫模块 - 默认笔趣阁API，可扩展"""
import asyncio
import httpx
import re
from typing import Optional, Tuple, List, Dict

DEFAULT_API = "https://apibi.cc/api/chapter"
CONCURRENCY = 50
TIMEOUT = 20.0
RETRIES = 3

WATERMARK_RE = re.compile(
    r'[a-zA-Z][a-zA-Z0-9]*[^a-zA-Z0-9\u4e00-\u9fff]*(?:cc|com|net|org|cn)\b',
    re.IGNORECASE
)

def _clean(txt):
    return WATERMARK_RE.sub('', txt)

def _split_paragraphs(txt):
    if not txt:
        return []
    txt = _clean(txt).replace("\r\n", "\n").replace("\r", "\n").strip()
    return [p.strip() for p in txt.split("\n") if p.strip()]


async def _fetch_one(client, sem, book_id, chapter_id, progress, api_url):
    async with sem:
        params = {"id": book_id, "chapterid": chapter_id}
        for attempt in range(1, RETRIES + 1):
            try:
                r = await client.get(api_url, params=params)
                r.raise_for_status()
                data = r.json()
                title = (data.get("chaptername") or "").strip()
                txt = (data.get("txt") or "").strip()
                if not title and not txt:
                    return None
                progress['done'] += 1
                return chapter_id, title or f"第{chapter_id}章", txt
            except Exception:
                await asyncio.sleep(0.3 * attempt)
        progress['fail'] += 1
        return None


async def crawl_book(book_id, chapter_start, chapter_end, book_name="未知",
                     api_url=DEFAULT_API, on_progress=None):
    """爬取一本书，返回 chapters 列表 [{id, title, content}]"""
    total = chapter_end - chapter_start + 1
    progress = {'done': 0, 'fail': 0, 'total': total}
    sem = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; CangJingGe/1.0)"},
        timeout=TIMEOUT, follow_redirects=True,
        limits=httpx.Limits(max_connections=CONCURRENCY + 10)
    ) as client:
        tasks = [
            _fetch_one(client, sem, book_id, cid, progress, api_url)
            for cid in range(chapter_start, chapter_end + 1)
        ]

        async def _monitor():
            while progress['done'] + progress['fail'] < progress['total']:
                await asyncio.sleep(0.5)
                if on_progress:
                    on_progress(progress['done'], progress['fail'], progress['total'])

        monitor = asyncio.create_task(_monitor())
        results = await asyncio.gather(*tasks)
        monitor.cancel()

    chapters = []
    for res in results:
        if res is None:
            continue
        cid, title, txt = res
        paragraphs = _split_paragraphs(txt)
        chapters.append({'id': cid, 'title': title, 'content': paragraphs})

    chapters.sort(key=lambda x: x['id'])
    return chapters, progress
