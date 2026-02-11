"""去水印模块"""
import re

# 内置水印规则
DOMAIN_WATERMARK = re.compile(
    r'[a-zA-Z]{2,}\d*\s*[^\w\u4e00-\u9fff]{0,3}\s*(?:com|cc|net|org)(?![a-zA-Z])',
    re.IGNORECASE
)
CN_DOT_WATERMARK = re.compile(
    r'[a-zA-Z]{2,}\d*\s*[点．]\s*(?:com|cc|net|org)(?![a-zA-Z])',
    re.IGNORECASE
)
ORPHAN_SYMBOLS = '♟•★♜⊙●○◇♀◆☆◎⊕♠■▤'
ORPHAN_PATTERN = re.compile(f'[{re.escape(ORPHAN_SYMBOLS)}]')
SENTENCE_WATERMARKS = [
    re.compile(r'本最新章节在首发[^"]*?去看[！!]?'),
    re.compile(r'请收藏本站[^"]*'),
    re.compile(r'手打更新最快[^"]*'),
]

CUSTOM_WATERMARKS = ['yuedu9點com']

def get_all_patterns(custom_watermarks=None):
    """返回所有水印规则列表 [(pattern, label)]"""
    patterns = [
        (DOMAIN_WATERMARK, '盗版站域名'),
        (CN_DOT_WATERMARK, '中文点域名'),
        (ORPHAN_PATTERN, '孤立特殊符号'),
    ]
    for i, p in enumerate(SENTENCE_WATERMARKS):
        patterns.append((p, f'整句水印#{i+1}'))

    # 使用自定义水印或默认水印
    watermarks_to_use = custom_watermarks if custom_watermarks else CUSTOM_WATERMARKS
    for t in watermarks_to_use:
        if t.strip():
            patterns.append((re.compile(re.escape(t)), f'手动: {t}'))
    return patterns

def clean_chapters(chapters, custom_watermarks=None):
    """清除章节内容中的水印，返回 (cleaned_chapters, total_removed)"""
    patterns = get_all_patterns(custom_watermarks)
    total = 0
    for ch in chapters:
        cleaned_content = []
        for para in ch.get('content', []):
            original = para
            for pattern, _ in patterns:
                para = pattern.sub('', para)
            if para != original:
                total += 1
            if para.strip():
                cleaned_content.append(para)
        ch['content'] = cleaned_content
    return chapters, total
