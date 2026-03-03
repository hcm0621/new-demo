# 知乎标题爬虫（保研经验贴）

这是一个纯 Python 标准库实现的小爬虫，用来抓取类似 `csbaoyan.top` 页面中的标题和链接。

## 用法

```bash
python zhihu_title_crawler.py \
  --url "https://csbaoyan.top/%E4%BF%9D%E7%A0%94%E7%BB%8F%E9%AA%8C%E8%B4%B4/2025%E5%B9%B4/" \
  --must-include-at-sign \
  --output zhihu_titles.txt
```

如果你只想抓取标题/链接中包含 `知乎` 的记录：

```bash
python zhihu_title_crawler.py --keyword 知乎 --output zhihu_titles.json --format json
```

## 主要参数

- `--url`：目标页面 URL。
- `--keyword`：只保留标题或链接里包含该关键词的记录。
- `--must-include-at-sign`：只保留标题中带 `@` 的记录（你给的样例就是这种格式）。
- `--output`：输出文件路径。
- `--format`：输出格式，支持 `txt` 或 `json`。
- `--html-file`：从本地 HTML 文件读取，便于离线调试。

## 输出格式

- `txt`：每行一个结果，格式为 `标题<TAB>链接`
- `json`：数组对象，字段为 `title` 与 `href`

## 说明

- 脚本对重复标题+链接做了去重。
- 为了降低依赖，未使用 `requests`、`beautifulsoup4` 等第三方库。
