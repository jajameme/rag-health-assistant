"""測試多輪聊天與檢索開關；使用假模型回答，避免每次等待數分鐘。"""

import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

from streamlit.testing.v1 import AppTest
import query

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

SOURCE = {
    "id": 1, "title": "測試新聞", "link": "https://www.healthnews.com.tw/article/69711",
    "summary": "測試摘要", "created_at": "2026-10-07T10:00:00+08:00",
}


class ChatTests(unittest.TestCase):
    def test_two_questions_then_summary_without_retrieval(self):
        with patch("query.retrieve_news", return_value=[SOURCE]) as retrieve, patch(
            "query.answer_question", return_value="測試回答"
        ) as answer:
            app = AppTest.from_file(APP_PATH, default_timeout=60).run()
            self.assertFalse(app.exception)
            for question in ("第一個問題", "第二個問題"):
                app.chat_input[0].set_value(question).run()
                self.assertFalse(app.exception)
            self.assertEqual(retrieve.call_count, 2)
            app.checkbox[0].uncheck().run()
            app.chat_input[0].set_value("整理剛才兩個問題").run()
            self.assertFalse(app.exception)
            self.assertEqual(retrieve.call_count, 2)  # 取消勾選後沒有再次檢索。
            self.assertEqual(len(answer.call_args.kwargs["history"]), 4)
            messages = app.session_state["messages"]
            self.assertEqual(len(messages), 6)
            self.assertFalse(messages[-1]["retrieved"])
            self.assertEqual(messages[-1]["sources"], [SOURCE])
            self.assertTrue(any(SOURCE["link"] in caption.value for caption in app.caption))
            app.button(key="clear_chat").click().run()
            self.assertEqual(app.session_state["messages"], [])

    def test_model_failure_does_not_save_partial_turn(self):
        with patch("query.retrieve_news", return_value=[SOURCE]), patch(
            "query.answer_question", side_effect=ConnectionError("Ollama 未啟動")
        ):
            app = AppTest.from_file(APP_PATH, default_timeout=60).run()
            app.chat_input[0].set_value("測試問題").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertEqual(app.session_state["messages"], [])

    def test_history_reaches_ollama_and_only_final_answer_is_used(self):
        history = [{"role": "user", "content": "先前問題"},
                   {"role": "assistant", "content": "先前回答"}]
        response = SimpleNamespace(done_reason="stop", message=SimpleNamespace(
            content="最後答案", thinking="不應顯示的思考"
        ))
        with patch("query.Client") as client:
            client.return_value.chat.return_value = response
            result = query.answer_question("整理重點", [SOURCE], history)
            self.assertEqual(result, "最後答案")
            messages = client.return_value.chat.call_args.kwargs["messages"]
            self.assertEqual(messages[1:3], history)
            self.assertIn(SOURCE["summary"], messages[-1]["content"])


if __name__ == "__main__":
    unittest.main()
