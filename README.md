# RAG 健康諮詢小幫手

自然語言處理課程作業：使用健康醫療網新聞、地端語言模型與向量檢索，建立具有多輪對話功能的網頁健康諮詢系統。

目前進度：已建立爬蟲、地端摘要、SQLite、向量索引、命令列 RAG 與多輪聊天網頁；正式作業展示仍需增加新聞及保存真實對話成果。

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
匯入 SQLite 時會自動產生流水號。

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

### 將新聞與摘要存入 SQLite

```powershell
.\.venv\Scripts\python.exe init_db.py
```

`init_db.py` 使用 Python 內建的 `sqlite3`，不需另裝資料庫伺服器。
讀取 `data/news_summarized.json`，建立 `data/news.db` 內的 `news` 資料表。

| 欄位 | 說明 |
|---|---|
| `id` | 自動產生的流水號 |
| `title` | 新聞標題 |
| `link` | 新聞連結，唯一值，用於避免重複新增 |
| `content` | 文章全文 |
| `summary` | 地端模型產生的摘要 |
| `created_at` | 首次取得資料的時間（沿用爬蟲欄位，UTC+8） |
| `published_at` | 新聞原始發布時間 |
| `summary_model` | 產生摘要的模型名稱 |

程式先確認必要欄位非空，再使用 SQL 參數寫入，確保含引號的文字可正確保存。
同連結重跑會更新文章與摘要，保留 `id`、`created_at`；本次 JSON 沒有的舊文章不會被刪除。
成功後顯示新增、更新與資料庫總筆數。若目前只完成一篇摘要，就只會匯入一篇。
日後修改資料庫摘要後，需要重新建立向量索引。

### 將標題與摘要轉成向量索引

安裝新增套件並建立索引：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe make_index.py
```

建立後順便測試搜尋：

```powershell
.\.venv\Scripts\python.exe make_index.py --query "低位直腸癌一定要做永久人工造口嗎？"
```

`make_index.py` 使用 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
作為中文 Embedding 模型，在 CPU 執行。千問負責摘要與問答，此模型負責文字轉向量。
第一次執行需連線下載模型，之後使用本機快取。

程式讀取 `news` 的 `id`、`title`、`summary`，將「新聞標題＋文章摘要」轉成向量。
使用正規化向量與 `IndexFlatIP`，內積即為 cosine similarity；`IndexIDMap` 保存新聞 ID。
每次從資料庫重新建立索引，不追加到舊索引，因此重跑不會累積重複向量。
索引存於 `data/vector.index`，模型名稱、維度及查詢前綴存於 `data/vector_metadata.json`。
FAISS 保存向量與 ID，原文、標題、連結與時間仍在 SQLite。

查詢必須使用相同模型並正規化，短問題依 BGE 官方建議加入查詢前綴，新聞文件不加。
模型有 token 上限，程式超出上限會停止並提示縮短摘要或改用長文本模型，避免靜默截斷。
相似度分數不是回答正確率；目前只有一篇新聞，測試只能驗證流程，無法評估多篇排序品質。

### 檢索新聞並交給千問回答

```powershell
.\.venv\Scripts\python.exe query.py --question "這篇新聞提到哪些因素會影響是否能保留肛門功能？"
```

只測試檢索，不呼叫千問：

```powershell
.\.venv\Scripts\python.exe query.py --question "人工造口" --retrieve-only
```

`retrieve_news()` 讀取索引，將問題轉成向量，取回最多三篇新聞的 ID，
再從 SQLite 取得標題、摘要與來源。`answer_question()` 把摘要放入千問提示詞，
要求根據資料回答；`format_sources()` 由程式在回答後條列真實新聞標題、連結與新增時間。
目前給模型的是摘要，不是全文；摘要未涵蓋的資訊可能無法回答。

請保持 Ollama 執行。可以用 `--top-k 1` 限制檢索篇數。
每次執行是獨立的一輪問答，尚無聊天記憶；多輪對話及檢索 checkbox 將在網頁階段加入。
目前沒有相關性門檻，即使問無關問題也會取得最接近的新聞，提示詞要求資料不足時明確說明，
但仍需人工核對回答，檢索到的來源不代表每個敘述都有充分依據。
資料庫標題或摘要變更後，請先重新執行 `make_index.py`。

### 啟動多輪聊天網頁

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

開啟 `http://localhost:8501`，並保持 Ollama 執行。
`app.py` 使用 Streamlit 的聊天元件，`st.session_state.messages` 保存目前瀏覽器連線的對話。
每次呼叫千問會傳入最近兩輪（四則訊息）的對話，頁面顯示完整聊天紀錄。

- 勾選「本輪檢索新聞」：結合近期問題與本輪問題搜尋，依檢索結果回答。
- 取消勾選：不呼叫向量檢索，依最近兩輪對話與先前來源摘要回答，並標示來源是沿用。
- 回答下方列出實際新聞標題、可點擊連結與文章新增時間。
- 「清除對話」移除本次瀏覽器連線的聊天紀錄；聊天不寫入硬碟。
- 呼叫失敗會顯示錯誤，不把失敗回合存入聊天歷史。

建議展示順序：

1. 勾選檢索，詢問「低位直腸癌一定要做永久人工造口嗎？」。
2. 保持檢索，詢問「哪些因素會影響是否能保留肛門功能？」。
3. 取消檢索，詢問「請整理剛才兩個問題的重點」。
4. 保存三次真實回答與來源的截圖，加入 README 成果。

目前只有一篇新聞，可展示流程，尚不能評估多篇檢索品質。
目前沒有相關性門檻；回答需核對摘要與原文。
網頁測試使用假模型驗證兩輪對話、關閉檢索、沿用來源、清除對話及錯誤處理：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 成果

- 爬蟲已實際取得三篇新聞，檢查連結不重複且標題、全文、時間欄位非空。
- 地端摘要已測試一篇，產生 244 字摘要，確認保存後仍保留原始新聞欄位。
- SQLite 已匯入一筆新聞，重跑仍維持一筆；另外驗證文字含引號、摘要更新及流水號與新增時間保留。
- FAISS 已建立一個 512 維向量，測試搜尋取得新聞 ID 1 及其來源，重建後仍為一個向量。
- 命令列 RAG 已實測「這篇新聞提到哪些因素會影響是否能保留肛門功能？」；千問產生回答，程式附上實際檢索的新聞標題、連結與新增時間。
- Streamlit 網頁服務已啟動驗證，三項自動測試通過（使用假模型）：兩輪後取消檢索並整理、模型失敗不保存回合、歷史傳入模型且只取最後答案。
- 網頁已加入多輪聊天、檢索 checkbox 與來源清單；正式三輪真實模型展示及截圖待補。
