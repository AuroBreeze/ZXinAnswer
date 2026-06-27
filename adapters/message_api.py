"""消息适配器 — 实现 MessagePort，封装未读计数和消息列表 HTTP 调用。"""

from typing import Any

import requests

import config
from adapters.auth_api import assert_api_ok
from domain.ports import MessagePort


class MessageApiAdapter(MessagePort):
    def get_unread_count(self, session: requests.Session) -> int:
        try:
            response = session.post(
                config.MESSAGE_API_URL,
                json={"action": "unreadCount"},
                timeout=10,
            )
            data = assert_api_ok(response)
            return int(data.get("data", {}).get("count", 0))
        except Exception:
            return 0

    def get_messages(self, session: requests.Session, page_num: int = 1, page_size: int = 20) -> list[dict]:
        try:
            response = session.post(
                config.MESSAGE_API_URL,
                json={"action": "studentList", "pageNum": page_num, "pageSize": page_size},
                timeout=10,
            )
            data = assert_api_ok(response)
            return data.get("data", {}).get("records", [])
        except Exception:
            return []