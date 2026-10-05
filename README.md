# RAG 健康諮詢小幫手

自然語言處理課程作業：使用健康醫療網新聞、地端語言模型與向量檢索，建立具有多輪對話功能的網頁健康諮詢系統。

目前進度：已建立 Git 專案、少量新聞爬蟲與地端摘要程式；資料庫、索引與網頁問答尚待實作。

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
正式資料庫的流水號將於後續步驟加入。

請求之間等待兩秒，連線錯誤會有限度重試；每成功取得一篇即保存。
每次執行會更新 JSON，並非累加。可調整 `--limit` 和 `--pages`，例如 `--limit 10 --pages 2`。
新聞資料供本機作業使用，`data/` 已從 Git 追蹤排除。

### 使用千問產生摘要

確認 Ollama 正在執行，先測試一篇：

```powershell
.\.venv\Scripts\python.exe summarize_news.py --limit 1
```

處理爬蟲 JSON 中的全部新聞：

```powershell
.\.venv\Scripts\python.exe summarize_news.py
```

`summarize_news.py` 讀取 `data/news_raw.json`，將每篇標題與全文放入提示詞，
透過本機 `http://localhost:11434` 呼叫 `qwen3:4b`。
本機模型模板在 `think=False` 下仍產生思考文字，因此使用 `think=True`，
讓 Ollama 將思考放在 `message.thinking`、最後答案放在 `message.content`；只保存答案。
取得 `response.message.content` 後，新增 `summary` 與 `summary_model` 欄位，
保存到 `data/news_summarized.json`，原始新聞檔保持原樣。

提示詞要求約 150～250 字的繁體中文摘要，這是本專案選擇，老師沒有規定摘要字數。
模型不一定精確遵守字數，也可能摘要錯誤，請核對原文。
程式逐篇保存本次結果，每次執行更新摘要檔；`--limit 1` 的結果只有一篇。
目前針對少量短新聞測試，尚未實作長文分段；長文超出上下文容量時需另外處理。
GTX 1650 4GB 的測試採 CPU/GPU 混合運算，首次摘要可能需要數分鐘。

## 成果

- 爬蟲已實際取得三篇新聞，檢查連結不重複且標題、全文、時間欄位非空。
- 地端摘要已測試一篇，產生 244 字摘要，確認保存後仍保留原始新聞欄位。
- 網頁問答、引用来源與多輪對話成果尚待實作及測試。
