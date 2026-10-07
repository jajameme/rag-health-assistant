"""第一步：從健康醫療網指定分類取得新聞，預設為中醫養生。"""

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
CHANNEL_URL = f"{BASE_URL}/channel/04558c00-7995-b05b-5c26-ef045abc9083"
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
    parser.add_argument("--channel-url", default=CHANNEL_URL, help="分類網址，可包含頁碼")
    parser.add_argument("--start-page", type=int, help="起始頁；未指定時使用網址頁碼或第 1 頁")
    args = parser.parse_args()
    # 把網址末尾的頁碼分離，例如 /channel/分類ID/3 從第 3 頁開始。
    # --start-page 若有指定，優先使用該值。只接受健康醫療網分類網址。
    match = re.fullmatch(
        r"https://www\.healthnews\.com\.tw/channel/([A-Za-z0-9-]+)(?:/(\d+))?/?",
        args.channel_url.strip(),
    )
    if match is None:
        parser.error("channel-url 必須是 https://www.healthnews.com.tw/channel/分類ID[/頁碼]")
    channel_url = f"{BASE_URL}/channel/{match.group(1)}"
    start_page = args.start_page if args.start_page is not None else int(match.group(2) or 1)
    if args.limit < 1 or args.pages < 1 or start_page < 1:
        parser.error("limit、pages 與起始頁必須大於 0")

    news = []
    seen = set()
    with requests.Session() as session:
        session.headers.update({"User-Agent": "RAGHealthAssistant-Educational/0.1"})
        session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
        )))
        for page in range(start_page, start_page + args.pages):
            if page > start_page:
                time.sleep(2)
            print(f"讀取分類第 {page} 頁")
            links = get_news_links(get_soup(session, f"{channel_url}/{page}"))
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
