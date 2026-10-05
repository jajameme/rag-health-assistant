# RAG 健康諮詢小幫手

自然語言處理課程作業：使用健康醫療網新聞、地端語言模型與向量檢索，建立具有多輪對話功能的網頁健康諮詢系統。

目前進度：已建立 Git 專案與少量新聞爬蟲；摘要、資料庫、索引與網頁問答尚待實作。

## 作業要求

- 使用網路爬蟲取得健康醫療網新聞分類的文章。
- 資料庫包含流水號、新聞標題、新聞連結、文章全文、文章摘要、文章新增時間。
- 使用地端模型，根據新聞標題與全文產生摘要。
- 將文章摘要轉成向量並建立向量索引。
- 整合地端模型與網頁問答介面，提供是否進行檢索的 checkbox。
- 展示兩個不同問題，以及整理前面對話重點的回答。
- 每次回答後條列檢索新聞的標題、連結與文章新增時間。

## 資料與範例來源

- 新聞來源：[健康醫療網](https://www.healthnews.com.tw/)
- 課程範例：[python_nlp](https://github.com/telunyang/python_nlp)，參考 `cases/RAG`。

## 執行方式

環境：Windows、Python 3.12.10、Ollama 0.35.1。地端模型使用 `qwen3:4b`。

在專案資料夾執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen3:4b
.\.venv\Scripts\python.exe crawl_news.py --limit 3 --pages 1
```

爬蟲預設取得大腸直腸癌分類第一頁的三篇新聞，存入 `data/news_raw.json`。
每篇保存 `title`、`link`、`content`、`published_at`（網站發布時間）與 `created_at`（取得資料時間，UTC+8）。
正式資料庫的流水號與摘要將於後續步驟加入。

請求之間等待兩秒，連線錯誤會有限度重試；每成功取得一篇即保存。
每次執行會更新 JSON，並非累加。可調整 `--limit` 和 `--pages`，例如 `--limit 10 --pages 2`。
新聞資料供本機作業使用，`data/` 已從 Git 追蹤排除。

## 成果

待實際執行後補上測試問題、回答、引用來源與截圖。
