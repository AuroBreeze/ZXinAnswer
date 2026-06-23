"""作业适配器 — 实现 HomeworkPort，封装 HTTP 调用。"""

from typing import Any

import requests

import config
from adapters.auth_api import assert_api_ok
from domain.entities import AnswerResult, Course, Homework, Question
from domain.exceptions import HomeworkError
from domain.ports import HomeworkPort


class HomeworkApiAdapter(HomeworkPort):
    def get_courses(self, session: requests.Session) -> list[Course]:
        response = session.post(config.CLASSROOM_API_URL, json=config.CLASSROOM_PAYLOAD, timeout=20)
        data = assert_api_ok(response)
        raw_courses = data.get("data", [])
        if not isinstance(raw_courses, list):
            raise HomeworkError(f"课程列表结构异常: {raw_courses!r}")
        return [Course.from_dict(c) for c in raw_courses]

    def get_homeworks(self, session: requests.Session, classroom_id: str) -> list[Homework]:
        records: list[dict] = []
        page_num = 1
        while True:
            payload = {
                "action": "studentPage",
                "classroomId": classroom_id,
                "pageNum": page_num,
                "pageSize": config.HOMEWORK_PAGE_SIZE,
                "orderBy": config.HOMEWORK_ORDER_BY,
                "order": config.HOMEWORK_ORDER,
            }
            response = session.post(config.HOMEWORK_API_URL, json=payload, timeout=20)
            data = assert_api_ok(response)
            try:
                page_records = self._extract_records(data)
            except HomeworkError:
                break
            records.extend(page_records)
            total = data.get("data", {}).get("total")
            if total is not None and len(records) >= int(total):
                break
            if len(page_records) < config.HOMEWORK_PAGE_SIZE:
                break
            page_num += 1
        return [Homework.from_dict(r) for r in records]

    def get_homework_detail(self, session: requests.Session, homework_id: str) -> list[Question]:
        response = session.post(
            config.HOMEWORK_DETAIL_API_URL,
            json={"action": "student", "homeworkId": homework_id},
            timeout=20,
        )
        data = assert_api_ok(response)
        try:
            questions = data["data"]["questions"]
        except (KeyError, TypeError) as exc:
            raise HomeworkError("作业详情响应结构不符合预期") from exc
        if not questions:
            raise HomeworkError("当前作业没有题目")
        return [Question.from_dict(q) for q in questions]

    def submit_answer(
        self, session: requests.Session, homework_id: str, question_id: str, mark: str
    ) -> AnswerResult:
        response = session.post(
            config.ANSWER_RECORD_API_URL,
            json={
                "action": "submit",
                "homeworkId": homework_id,
                "questionId": question_id,
                "options": [{"mark": mark, "content": ""}],
            },
            timeout=20,
        )
        data = assert_api_ok(response)
        return AnswerResult.from_dict(data)

    @staticmethod
    def _extract_records(homework_data: dict) -> list[dict]:
        try:
            records = homework_data["data"]["records"]
        except (KeyError, TypeError) as exc:
            raise HomeworkError("作业列表响应结构不符合预期") from exc
        if not records:
            raise HomeworkError("当前课程没有作业")
        return records