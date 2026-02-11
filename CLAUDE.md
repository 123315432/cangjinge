# 藏经阁项目指令

## 项目概述
小说阅读器桌面应用，整合自"没钱修什么仙"项目，集成爬虫、去水印、多设备同步功能。

## 技术架构

### 后端 (server.py)
- Python ThreadingHTTPServer
- RESTful API + SSE
- Gzip压缩 + ETag缓存
- 多线程爬虫（asyncio + aiohttp）
- 进度同步：最高章节优先，时间戳作为平局决胜

### 前端 (web/)
- 原生HTML/CSS/JS（无框架）
- PWA支持（Service Worker + manifest）
- 7种主题 + 视觉效果
- 响应式设计

### 桌面应用 (app.py)
- pywebview包装本地HTTP服务器
- 无边框窗口，原生体验

## 核心功能

### 1. 书籍管理
- 添加书籍：书名、book_id、章节范围、API地址
- 自动生成唯一ID：md5(book_id_start_end)[:12]
- 数据存储：data/books.json

### 2. 章节爬取 (crawler.py)
- 异步并发爬取（最多10并发）
- 实时进度回调
- 错误重试机制
- 返回格式：(chapters, progress)

### 3. 水印清除 (watermark.py)
- 手动指定水印列表（每行一个）
- 内置规则：域名、中文点域名、孤立符号、整句水印
- 自定义水印优先级最高

### 4. 多设备同步
- SSE长连接推送进度更新
- 同步逻辑：
  ```python
  if cur_chapter > new_chapter: reject  # 章节数优先
  if cur_chapter == new_chapter and cur_ts >= new_ts: reject  # 时间戳决胜
  ```
- 客户端自动抑制旧数据推送

## API端点

### GET
- `/` - 书架页
- `/read/{id}` - 阅读页
- `/api/books` - 书籍列表（含进度）
- `/api/books/{id}/chapters` - 章节列表（Gzip + ETag）
- `/api/books/{id}/progress` - 读取进度
- `/api/crawl/status` - 爬虫状态
- `/api/progress/stream` - SSE进度流

### POST
- `/api/books/{id}/progress` - 保存进度 {chapter, ts}
- `/api/books/add` - 添加书籍并爬取
- `/api/books/{id}/clean` - 清除水印 {watermarks: []}

## 数据结构

### books.json
```json
[{
  "id": "190937abc123",
  "name": "书名",
  "author": "作者",
  "source": "来源",
  "book_id": 190937,
  "chapter_count": 900,
  "chapter_start": 1,
  "chapter_end": 900
}]
```

### progress.json
```json
{
  "190937abc123": {
    "chapter": 283,
    "ts": 1770811875296
  }
}
```

### chapters/{id}.json
```json
[{
  "index": 0,
  "title": "第一章",
  "content": ["段落1", "段落2"]
}]
```

## 开发规范

### 编码
- UTF-8编码
- CRLF换行（Windows）
- 中文注释

### 错误处理
- API返回统一格式：{ok: bool, msg?: string, data?: any}
- HTTP状态码：200成功，404不存在，409冲突

### 性能优化
- 章节数据Gzip压缩（~4.8MB → ~400KB）
- ETag缓存（304 Not Modified）
- SSE心跳30秒

### 安全
- 不提交data/目录（包含用户数据）
- 不提交__pycache__
- 本地使用，无需认证

## 常见问题

### 端口冲突
默认8080，可通过命令行参数修改：
```bash
python server.py 8000
```

### 水印扫描失败
使用手动水印输入功能，在弹窗中输入具体水印文字（每行一个）

### 进度同步冲突
采用"最高章节优先"策略，自动选择阅读进度最快的设备

## 依赖
- Python 3.10+
- aiohttp
- pywebview

## 启动方式
```bash
# 浏览器模式
python server.py [port]

# 桌面应用
python app.py
```
