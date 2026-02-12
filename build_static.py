"""
藏经阁 - 静态化构建脚本
读取 data/ 目录，生成 dist/ 用于 Vercel 部署
"""
import json, os, shutil
from pathlib import Path

CHUNK_SIZE = 50  # 每个分块文件包含的章节数
SRC = Path(__file__).parent
DATA = SRC / "data"
DIST = SRC / "dist"


def build():
    # 清理 dist（保留 .git）
    if DIST.exists():
        for item in DIST.iterdir():
            if item.name == '.git':
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        DIST.mkdir()

    # 读取书籍列表
    books = json.loads((DATA / "books.json").read_text("utf-8"))

    # 生成每本书的静态数据
    for book in books:
        bid = str(book["id"])
        book_dir = DATA / "books" / bid
        if not book_dir.exists():
            print(f"跳过 {bid}: 数据目录不存在")
            continue

        chapters_file = book_dir / "chapters.json"
        if not chapters_file.exists():
            print(f"跳过 {bid}: chapters.json 不存在")
            continue

        chapters = json.loads(chapters_file.read_text("utf-8"))
        api_dir = DIST / "api" / "books" / bid
        chunks_dir = api_dir / "chunks"
        chunks_dir.mkdir(parents=True)

        # meta.json: 仅标题
        meta = [{"index": i, "id": ch.get("id", i + 1), "title": ch["title"]}
                for i, ch in enumerate(chapters)]
        (api_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), "utf-8")

        # 分块 chunks/0.json, 1.json, ...
        total_chunks = (len(chapters) + CHUNK_SIZE - 1) // CHUNK_SIZE
        for ci in range(total_chunks):
            start = ci * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(chapters))
            chunk = [{"id": ch.get("id", i + 1), "title": ch["title"],
                       "content": ch["content"]}
                     for i, ch in enumerate(chapters[start:end], start)]
            (chunks_dir / f"{ci}.json").write_text(
                json.dumps(chunk, ensure_ascii=False), "utf-8")

        # 读取进度写入 books.json
        prog_file = book_dir / "progress.json"
        if prog_file.exists():
            book["progress"] = json.loads(prog_file.read_text("utf-8"))

        book["chunk_size"] = CHUNK_SIZE
        book["total_chunks"] = total_chunks
        print(f"  {book['name']}: {len(chapters)} 章 → {total_chunks} 个分块")

    # books.json
    (DIST / "api").mkdir(exist_ok=True)
    (DIST / "api" / "books.json").write_text(
        json.dumps(books, ensure_ascii=False, indent=2), "utf-8")

    # 复制静态资源
    for f in ["manifest.json", "sw.js"]:
        src = SRC / "web" / f
        if src.exists():
            shutil.copy2(src, DIST / f)

    # icons 目录
    icons_src = SRC / "icons"
    if icons_src.exists():
        shutil.copytree(icons_src, DIST / "icons", dirs_exist_ok=True)

    # vercel.json
    vercel_config = {
        "rewrites": [
            {"source": "/read/:id", "destination": "/reader.html"}
        ],
        "headers": [
            {
                "source": "/api/(.*)",
                "headers": [
                    {"key": "Cache-Control", "value": "public, max-age=86400"},
                    {"key": "Access-Control-Allow-Origin", "value": "*"}
                ]
            }
        ]
    }
    (DIST / "vercel.json").write_text(
        json.dumps(vercel_config, indent=2), "utf-8")

    print(f"\n构建完成 → {DIST}")
    print(f"  总文件数: {sum(1 for _ in DIST.rglob('*') if _.is_file())}")
    total_size = sum(f.stat().st_size for f in DIST.rglob('*') if f.is_file())
    print(f"  总大小: {total_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    build()
