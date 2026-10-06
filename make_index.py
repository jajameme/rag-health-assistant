"""第四步：將新聞標題與摘要轉成向量，重新建立 FAISS 索引。"""

import argparse  # 讀取命令列參數，例如 --query
import json
import sqlite3
import sys
from pathlib import Path

import faiss  # 保存向量，並搜尋最相近的向量
import numpy as np  # 處理數字陣列，配合 FAISS 要求的資料型態
from sentence_transformers import SentenceTransformer  # 將文字轉成向量的模型

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "data" / "news.db"
INDEX_PATH = PROJECT_DIR / "data" / "vector.index"
METADATA_PATH = PROJECT_DIR / "data" / "vector_metadata.json"

# 這是中文 Embedding 模型，不是用來回答問題的千問。
# 使用較小的模型搭配 CPU，避免與千問爭用 4GB 顯示記憶體。
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
# BGE 官方建議：短問題加上這個前綴，新聞文件則不加。
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def load_documents(db_path):
    """取得新聞 ID 與『標題＋摘要』，全文仍保留在 SQLite。"""
    if not db_path.exists():
        raise FileNotFoundError("找不到 news.db，請先執行 init_db.py")

    # 唯讀連線：路徑錯誤時不會意外建立空白資料庫。
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id, title, summary FROM news ORDER BY id").fetchall()
    finally:
        conn.close()
    if not rows:
        raise ValueError("資料庫沒有新聞，請先匯入摘要")

    docs = []  # 每一筆是要轉成向量的文字
    doc_ids = []  # 每一筆是對應的新聞 ID，順序必須與 docs 相同
    for news_id, title, summary in rows:
        if not all(isinstance(text, str) and text.strip() for text in (title, summary)):
            raise ValueError(f"新聞 ID {news_id} 缺少標題或摘要，請先補齊")
        docs.append(f"新聞標題：{title}\n文章摘要：{summary}")
        doc_ids.append(news_id)
    return docs, np.asarray(doc_ids, dtype="int64")


def build_index(encoder, docs, doc_ids):
    """計算向量並建立全新索引，不讀取舊索引來追加。"""
    # 模型有文字長度上限；先檢查，避免摘要過長被悄悄截斷。
    for news_id, text in zip(doc_ids, docs):
        tokens = encoder.tokenizer(text, truncation=False)["input_ids"]
        if len(tokens) > encoder.max_seq_length:
            raise ValueError(
                f"新聞 ID {news_id} 有 {len(tokens)} tokens，超過模型上限 "
                f"{encoder.max_seq_length}；請縮短摘要或改用長文本模型"
            )

    # encode 把文字清單轉成二維數字陣列，每一列代表一篇新聞。
    # normalize_embeddings=True 將向量長度調成 1。
    embeddings = encoder.encode(
        docs, batch_size=8, show_progress_bar=True,
        normalize_embeddings=True, convert_to_numpy=True,
    )
    # FAISS 需要 float32 向量及 int64 ID；連續陣列方便底層讀取。
    embeddings = np.ascontiguousarray(embeddings, dtype="float32")
    dimensions = embeddings.shape[1]  # 取得每個向量有多少個數字

    # IndexFlatIP 使用內積比較；向量已正規化，因此等同 cosine similarity。
    # IndexIDMap 讓搜尋結果回傳 SQLite 新聞 ID，而不是陣列的列號。
    index = faiss.IndexIDMap(faiss.IndexFlatIP(dimensions))
    index.add_with_ids(embeddings, doc_ids)
    return index


def search_news(encoder, index, query, db_path, top_k=3):
    """測試搜尋：問題轉成向量，再用搜尋到的 ID 取得新聞來源。"""
    query_vector = encoder.encode(
        [QUERY_PREFIX + query], normalize_embeddings=True, convert_to_numpy=True
    )
    query_vector = np.ascontiguousarray(query_vector, dtype="float32")
    # 索引只有一篇時就只找一篇，避免請求三篇而得到無效的 -1 ID。
    scores, ids = index.search(query_vector, min(top_k, index.ntotal))
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        for news_id, score in zip(ids[0], scores[0]):
            row = conn.execute(
                "SELECT title, link, created_at FROM news WHERE id = ?", (int(news_id),)
            ).fetchone()
            if row is None:
                raise ValueError("索引的新聞 ID 在資料庫找不到，請重新建立索引")
            title, link, created_at = row
            # 分數是語意相似度，不是回答正確率或醫療可信度。
            print(f"ID {news_id}｜相似度 {score:.4f}｜{title}")
            print(f"  連結：{link}\n  新增時間：{created_at}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="建立索引後，額外測試一個搜尋問題")
    args = parser.parse_args()
    docs, doc_ids = load_documents(DB_PATH)
    print(f"讀取 {len(docs)} 篇新聞，載入 Embedding 模型：{MODEL_NAME}", flush=True)
    # 第一次會從 Hugging Face 下載模型，以後使用本機快取。
    encoder = SentenceTransformer(MODEL_NAME, device="cpu")
    index = build_index(encoder, docs, doc_ids)

    # 先寫暫存檔再替換舊索引；重新執行不會重複追加新聞。
    temporary = INDEX_PATH.with_suffix(".tmp")
    faiss.write_index(index, str(temporary))
    temporary.replace(INDEX_PATH)
    # 記錄模型與設定，後續提問必須使用相同 Embedding 模型與正規化方式。
    metadata = {
        "model_name": MODEL_NAME,
        "dimensions": index.d,
        "document_count": index.ntotal,
        "text_fields": ["title", "summary"],
        "normalize_embeddings": True,
        "query_prefix": QUERY_PREFIX,
    }
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成！索引有 {index.ntotal} 個向量，每個 {index.d} 維。")
    print(f"索引位置：{INDEX_PATH}")
    if args.query:
        # 重新讀取已保存的檔案，確認磁碟上的索引也可以搜尋。
        print(f"\n測試問題：{args.query}")
        saved_index = faiss.read_index(str(INDEX_PATH))
        search_news(encoder, saved_index, args.query, DB_PATH)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    main()
