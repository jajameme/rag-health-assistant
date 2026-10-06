"""第三步：把新聞與千問摘要存入 SQLite 資料庫。"""

import json  # 將 JSON 文字轉成 Python 資料
import sqlite3  # Python 內建的 SQLite 套件，不需要另外安裝
import sys
from pathlib import Path  # 處理檔案路徑

# 使用程式所在位置組合路徑，從其他資料夾執行也能找到資料。
PROJECT_DIR = Path(__file__).resolve().parent
INPUT_PATH = PROJECT_DIR / "data" / "news_summarized.json"
DB_PATH = PROJECT_DIR / "data" / "news.db"


def load_news(input_path):
    """讀取摘要 JSON，先確認所有新聞都有必要欄位。"""
    if not input_path.exists():
        raise FileNotFoundError("找不到 news_summarized.json，請先執行 summarize_news.py")

    # read_text 讀出文字；json.loads 將文字轉成清單，清單內每筆是字典。
    news_data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(news_data, list) or not news_data:
        raise ValueError("新聞資料必須是非空的 JSON 清單")

    required_fields = ("title", "link", "content", "summary", "created_at")
    for number, news in enumerate(news_data, start=1):
        if not isinstance(news, dict):
            raise ValueError(f"第 {number} 筆新聞必須是字典")
        for field in required_fields:
            value = news.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"第 {number} 筆新聞的 {field} 必須是非空字串")
        # 以下是額外欄位，可以缺少或為 None，但不能填入清單等其他型態。
        for field in ("published_at", "summary_model"):
            value = news.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"第 {number} 筆新聞的 {field} 必須是字串或 null")
    return news_data


def create_table(conn):
    """建立 news 資料表；已存在時保留原本資料。"""
    # execute 執行一段 SQL。三個引號讓 SQL 可以分行，方便閱讀。
    # PRIMARY KEY：用 id 識別每筆新聞；AUTOINCREMENT：自動產生流水號。
    # UNIQUE：同一個連結只能有一筆新聞；NOT NULL：不允許欄位為空值。
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            published_at TEXT,
            summary_model TEXT
        )
    """)


def insert_news_data(conn, news_data):
    """依新聞連結判斷：新文章新增，已有文章更新內容與摘要。"""
    inserted = 0
    updated = 0
    for news in news_data:
        # ? 是參數位置，不用 f 字串把新聞塞進 SQL。
        # 這樣標題或內文即使含有引號，也能正確保存。
        # (news["link"],) 是只有一個元素的 tuple，結尾逗號不可省略。
        existing = conn.execute(
            "SELECT id FROM news WHERE link = ?", (news["link"],)
        ).fetchone()  # fetchone 取得一筆結果；找不到時回傳 None。

        if existing is None:
            conn.execute("""
                INSERT INTO news
                    (title, link, content, summary, created_at, published_at, summary_model)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                news["title"], news["link"], news["content"], news["summary"],
                news["created_at"], news.get("published_at"), news.get("summary_model"),
            ))
            inserted += 1
        else:
            # 重跑時更新新聞，但保留原流水號與首次取得資料的 created_at。
            # 不刪除本次 JSON 沒包含的其他新聞。
            conn.execute("""
                UPDATE news
                SET title = ?, content = ?, summary = ?, published_at = ?, summary_model = ?
                WHERE id = ?
            """, (
                news["title"], news["content"], news["summary"],
                news.get("published_at"), news.get("summary_model"), existing[0],
            ))
            updated += 1
    return inserted, updated


def main():
    # 先檢查全部輸入，再連接資料庫，避免匯入一半才發現缺少摘要。
    news_data = load_news(INPUT_PATH)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)  # 檔案不存在時，SQLite 會建立它。
    try:
        # with conn 是交易：全部成功才提交，出錯則撤回本次資料修改。
        # 它不會自動關閉連線，因此最後仍要執行 conn.close()。
        with conn:
            create_table(conn)
            inserted, updated = insert_news_data(conn, news_data)

        total = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        print(f"完成！新增 {inserted} 筆，更新 {updated} 筆，資料庫共 {total} 筆。")
        print(f"資料庫位置：{DB_PATH}")
        print("以下列出資料庫內的新聞：")
        for news_id, title, length in conn.execute(
            "SELECT id, title, LENGTH(summary) FROM news ORDER BY id"
        ):
            print(f"  ID {news_id}｜{title}｜摘要 {length} 字")
    finally:
        conn.close()  # 不論成功或失敗，都釋放資料庫連線。


# 直接執行此檔案時才呼叫 main；被其他程式匯入時不會自動寫入資料庫。
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"匯入失敗：{exc}", file=sys.stderr)
        sys.exit(1)  # 非零結束碼表示執行失敗。
