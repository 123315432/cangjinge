#!/usr/bin/env python3
"""把藏经阁阅读器打包成独立HTML，章节数据内嵌，离线可用"""
import json, re, sys
from pathlib import Path

CANGJINGE = Path(__file__).parent
DATA_DIR = CANGJINGE / "data"
READER_HTML = CANGJINGE / "reader.html"


def build(book_id, output=None):
    book_dir = DATA_DIR / "books" / book_id
    chapters_file = book_dir / "chapters.json"
    if not chapters_file.exists():
        print(f"找不到: {chapters_file}")
        return

    books = json.loads((DATA_DIR / "books.json").read_text("utf-8"))
    book_info = next((b for b in books if b.get("id") == book_id), {})
    book_name = book_info.get("name", book_id)

    chapters = json.loads(chapters_file.read_text("utf-8"))
    print(f"书名: {book_name}, 章节: {len(chapters)}")

    html = READER_HTML.read_text("utf-8")

    # 替换标题
    html = html.replace("<title>阅读 - 藏经阁</title>", f"<title>{book_name} - 藏经阁</title>")

    # 移除Google Fonts外链(离线用不了)
    html = re.sub(r'<link rel="preconnect"[^>]*>\n?', '', html)
    html = re.sub(r'<link href="https://fonts\.googleapis\.com[^>]*>\n?', '', html)

    # 把章节数据放到单独的JSON script标签里(JSON.parse比JS字面量快10倍)
    ch_json = json.dumps(chapters, ensure_ascii=False)
    json_tag = f'<script type="application/json" id="chData">{ch_json}</script>'
    html = html.replace('</head>', f'{json_tag}\n</head>')

    inline_boot = """
// ===== Standalone: embedded data =====
var raw = JSON.parse(document.getElementById('chData').textContent);
chapters = raw.map(function(ch, i) {
  return { index: i, id: i + 1, title: ch.title, content: ch.content };
});
if (currentIndex >= chapters.length) currentIndex = 0;
loading.classList.add('hide');
loading.style.display = 'none';
init();
"""

    # 替换原来的fetch boot逻辑
    html = re.sub(
        r'// 加载章节元数据.*?(?=</script>)',
        inline_boot,
        html,
        flags=re.DOTALL
    )

    # 让ensureChapterLoaded和loadChunk变成空操作(数据已内嵌)
    html = html.replace(
        'async function loadChunk(chunkIndex) {',
        'async function loadChunk(chunkIndex) { return; '
    )

    # 返回书架改为回到第一章
    html = html.replace('href="/"', 'href="javascript:goChapter(0)"')

    out = Path(output) if output else (book_dir / f"{book_name}.html")
    out.write_text(html, encoding="utf-8")
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"生成: {out}")
    print(f"大小: {size_mb:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python build_standalone.py <book_id> [输出路径]")
        print("示例: python build_standalone.py guke_chunai")
        sys.exit(1)
    bid = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    build(bid, out)
