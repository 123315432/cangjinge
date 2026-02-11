"""从现有 没钱修什么仙.html 提取章节数据到 JSON"""
import json
import os
import sys

SRC = r"C:\Users\69406\PycharmProjects\PythonProject\meiqianxiushenmxian\没钱修什么仙.html"
DST_DIR = os.path.join(os.path.dirname(__file__), "data", "books", "190937")
BOOKS_JSON = os.path.join(os.path.dirname(__file__), "data", "books.json")

def extract():
    with open(SRC, 'r', encoding='utf-8') as f:
        content = f.read()

    marker = 'const chapters = '
    idx = content.find(marker)
    if idx == -1:
        print("找不到 chapters 数据")
        sys.exit(1)

    json_start = content.find('[', idx)
    # 找到匹配的 ]
    depth = 0
    i = json_start
    while i < len(content):
        ch = content[i]
        if ch == '[': depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                json_end = i + 1
                break
        elif ch == '"':
            i += 1
            while i < len(content):
                if content[i] == '\\': i += 2; continue
                if content[i] == '"': break
                i += 1
        i += 1

    chapters = json.loads(content[json_start:json_end])
    print(f"提取到 {len(chapters)} 章")

    os.makedirs(DST_DIR, exist_ok=True)
    with open(os.path.join(DST_DIR, "chapters.json"), 'w', encoding='utf-8') as f:
        json.dump(chapters, f, ensure_ascii=False)

    # 初始化 books.json
    books = [{
        "id": "190937",
        "name": "没钱修什么仙",
        "author": "佚名",
        "source": "apibi.cc",
        "book_id": 190937,
        "chapter_count": len(chapters),
        "chapter_start": 1,
        "chapter_end": len(chapters),
    }]
    os.makedirs(os.path.dirname(BOOKS_JSON), exist_ok=True)
    with open(BOOKS_JSON, 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=2)

    print(f"已保存到 {DST_DIR}")
    print(f"书库元数据: {BOOKS_JSON}")

if __name__ == '__main__':
    extract()
