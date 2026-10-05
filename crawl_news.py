"""第一步：從健康醫療網大腸直腸癌分類取得少量新聞。"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.healthnews.com.tw"
CHANNEL_URL = f"{BASE_URL}/channel/9b508eee-a171-75b6-0963-eec4e463fc46"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "news_raw.json"


def get_soup(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "lxml")


def get_news_links(soup):
    """只選取新聞列表內的文章連結，不抓廣告或導覽連結。"""
    links = []
    for item in soup.select("ul.list-unstyled > li.list-item"):
        anchor = item.select_one(".list-title > a[href]")
        if anchor is None:
            continue
        link = urljoin(BASE_URL, anchor["href"])
        if re.fullmatch(r"https://www\.healthnews\.com\.tw/article/\d+/?", link):
            links.append(link.rstrip("/"))
    return list(dict.fromkeys(links))


def parse_article(soup, link):
    title_node = soup.select_one("#article-title")
    content_node = soup.select_one("#article-content")
    if title_node is None or content_node is None:
        raise ValueError("找不到新聞標題或全文，請檢查網站結構")
    for unwanted in content_node.select("script, style"):
        unwanted.decompose()
    title = title_node.get_text(" ", strip=True)
    content = content_node.get_text("\n", strip=True)
    if not title or not content:
        raise ValueError("新聞標題或全文為空")
    published = soup.select_one('meta[property="article:published_time"]')
    return {
        "title": title,
        "link": link,
        "content": content,
        "published_at": published.get("content") if published else None,
        # created_at 是本次取得資料的時間，與新聞原始發布時間分開保存。
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }


def save_news(news):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT_PATH)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=3, help="最多取得幾篇新聞，預設 3")
    parser.add_argument("--pages", type=int, default=1, help="最多讀取幾頁分類，預設 1")
    args = parser.parse_args()
    if args.limit < 1 or args.pages < 1:
        parser.error("limit 與 pages 必須大於 0")

    news = []
    seen = set()
    with requests.Session() as session:
        session.headers.update({"User-Agent": "RAGHealthAssistant-Educational/0.1"})
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
        )))
        for page in range(1, args.pages + 1):
            if page > 1:
                time.sleep(2)
            print(f"讀取分類第 {page} 頁")
            links = get_news_links(get_soup(session, f"{CHANNEL_URL}/{page}"))
            if not links:
                raise RuntimeError("分類頁找不到新聞連結，請檢查網址或網站結構")
            for link in links:
                if link in seen:
                    continue
                seen.add(link)
                time.sleep(2)
                try:
                    article = parse_article(get_soup(session, link), link)
                except (requests.RequestException, ValueError) as exc:
                    print(f"略過 {link}：{exc}", file=sys.stderr)
                    continue
                news.append(article)
                save_news(news)
                print(f"[{len(news)}] {article['title']}")
                print(f"    全文 {len(article['content'])} 字；發布時間 {article['published_at']}")
                if len(news) >= args.limit:
                    break
            if len(news) >= args.limit:
                break
    if not news:
        raise RuntimeError("未取得任何文章")
    print(f"已儲存 {len(news)} 篇新聞：{OUTPUT_PATH}")
    print("再次執行會更新這份 JSON；摘要與資料庫將在後續步驟加入。")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    main()
