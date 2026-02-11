# 藏经阁

小说阅读器桌面应用，集成爬虫、去水印、多设备同步功能。

## 功能特性

- 📚 多书籍管理
- 🕷️ 自动章节爬取
- 🧹 手动水印清除
- 🔄 SSE多设备同步（最高章节优先）
- 🎨 7种主题+视觉效果
- 💻 pywebview桌面应用
- 📱 PWA移动端支持

## 快速开始

```bash
# 启动服务器（默认8000端口）
python server.py

# 指定端口
python server.py 8080

# 启动桌面应用
python app.py
```

## 访问地址

- 浏览器：http://localhost:8000
- 桌面应用：运行 app.py

## 项目结构

```
藏经阁/
├── server.py       # HTTP服务器+API
├── app.py          # pywebview桌面应用
├── crawler.py      # 章节爬虫
├── watermark.py    # 水印清除
├── migrate.py      # 数据迁移
├── web/            # 前端文件
│   ├── index.html  # 书架页
│   ├── reader.html # 阅读页
│   ├── sw.js       # Service Worker
│   └── manifest.json
└── data/           # 数据存储（已忽略）
    ├── books.json
    ├── progress.json
    └── chapters/
```

## 技术栈

- Python 3.10+
- pywebview
- asyncio + aiohttp
- SSE (Server-Sent Events)
- PWA
