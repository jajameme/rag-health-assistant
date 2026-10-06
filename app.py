"""第六步：使用 Streamlit 建立多輪 RAG 健康新聞聊天網頁。"""

import streamlit as st  # 提供網頁元件與每個使用者各自的聊天狀態

from query import answer_question, retrieve_news
from make_index import DB_PATH, INDEX_PATH, METADATA_PATH


def previous_sources(messages):
    """取得最近兩輪實際用過的來源，關閉檢索時可沿用並整理對話。"""
    sources = {}  # 用新聞 ID 去除重複，來源始終來自資料庫檢索結果。
    for message in messages[-4:]:
        for article in message.get("sources", []):
            sources[article["id"]] = article
    return list(sources.values())[:3]


def show_sources(sources, retrieved):
    """在回答後顯示來源；區分本輪檢索與沿用前面對話的來源。"""
    label = "本輪檢索新聞來源" if retrieved else "沿用先前對話的新聞來源（本輪未檢索）"
    st.markdown(f"**{label}**")
    if not sources:
        st.caption("本輪未檢索，也沒有先前新聞來源。")
    for number, article in enumerate(sources, start=1):
        # 不讓模型自己生成 URL。標題用 text 顯示，避免新聞標題被當 Markdown。
        st.text(f"• [新聞 {number}] {article['title']}")
        st.link_button("閱讀原文", article["link"])
        st.caption(f"新聞連結：{article['link']}")
        st.caption(f"文章新增時間：{article['created_at']}")


def main():
    st.set_page_config(page_title="RAG 健康諮詢小幫手", page_icon="📰", layout="centered")
    st.title("📰 健康諮詢小幫手")
    st.caption("根據健康新聞整理資訊，回答附新聞來源。資訊供參考，不能代替醫師診斷。")

    # Streamlit 操作元件時會重新執行程式，session_state 可保留聊天。
    # 每個瀏覽器連線各有一份狀態，不使用全域清單混用不同人的對話。
    if "messages" not in st.session_state:
        st.session_state.messages = []

    ready = all(path.exists() for path in (DB_PATH, INDEX_PATH, METADATA_PATH))
    with st.sidebar:
        st.header("對話設定")
        use_retrieval = st.checkbox("本輪檢索新聞", value=True, key="use_retrieval")
        st.caption("勾選：查詢新聞後回答。取消：依最近兩輪對話與先前來源回答，適合整理重點。")
        top_k = st.selectbox("最多檢索篇數", [1, 2, 3], index=2, disabled=not use_retrieval)
        if st.button("清除對話", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()
        st.caption("聊天不寫入硬碟，重新整理頁面可能清除。模型使用最近兩輪對話。")

    if not ready:
        st.warning("尚未準備好新聞資料庫或索引，請先執行 init_db.py 與 make_index.py。")
    if not st.session_state.messages:
        st.info("先詢問兩個新聞相關問題，再取消檢索，輸入「請整理剛才兩個問題的重點」。")

    # 重新顯示所有已成功完成的對話；每個回答保留當時來源及檢索設定。
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                show_sources(message["sources"], message["retrieved"])

    question = st.chat_input("輸入新聞問題，或請我整理剛才的對話…", max_chars=200,
                             disabled=use_retrieval and not ready, submit_mode="disable")
    if question and question.strip():
        with st.chat_message("user"):
            st.write(question)
        try:
            with st.chat_message("assistant"):
                with st.spinner("正在整理資料並請千問回答，可能需要數分鐘…"):
                    history = st.session_state.messages[-4:]
                    if use_retrieval:
                        # 把最近問題加到查詢，讓「那治療呢？」等追問有主題線索。
                        prior_questions = [m["content"][:80] for m in history if m["role"] == "user"]
                        search_text = "\n".join(prior_questions + [question])
                        sources = retrieve_news(search_text, top_k)
                    else:
                        # 這個分支完全不呼叫 retrieve_news；不是只把來源藏起來。
                        sources = previous_sources(history)
                    answer = answer_question(question, sources, history=history)
                st.markdown(answer)
                show_sources(sources, use_retrieval)

            # 只有成功回答才一起保存 user 與 assistant，錯誤不污染聊天歷史。
            st.session_state.messages.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer,
                 "sources": sources, "retrieved": use_retrieval},
            ])
        except Exception as exc:
            # 例如 Ollama 未啟動或索引缺失，讓使用者看見錯誤並可重試。
            st.error(f"回答失敗：{exc}")
            st.caption("請確認 Ollama 正在執行、qwen3:4b 已下載，以及新聞索引已建立。")


if __name__ == "__main__":
    main()
