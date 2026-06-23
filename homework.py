"""作业 & 答题：课程/作业/题目/提交相关 API 及数据处理。"""

import re
from typing import Any

import requests

from auth import ApiError, assert_api_ok, CLASSROOM_API_URL, CLASSROOM_PAYLOAD

HOMEWORK_API_URL = "https://stu.z-xin.net/api/homework"
HOMEWORK_DETAIL_API_URL = "https://stu.z-xin.net/api/homework/detail"
ANSWER_RECORD_API_URL = "https://stu.z-xin.net/api/answer-record"

ACTION_STUDENT_PAGE = "studentPage"
ACTION_STUDENT = "student"
ACTION_SUBMIT = "submit"

HOMEWORK_PAGE_SIZE = 20
HOMEWORK_ORDER_BY = "createTime"
HOMEWORK_ORDER = "desc"


def get_classroom_data(session: requests.Session) -> list[dict]:
    response = session.post(CLASSROOM_API_URL, json=CLASSROOM_PAYLOAD, timeout=20)
    data = assert_api_ok(response)
    courses = data.get("data", [])
    if not isinstance(courses, list):
        raise ApiError(f"课程列表结构异常: {courses!r}")
    return courses


def fetch_homework_page(
    session: requests.Session, classroom_id: str, page_num: int, page_size: int
) -> dict[str, Any]:
    payload = {
        "action": ACTION_STUDENT_PAGE,
        "classroomId": classroom_id,
        "pageNum": page_num,
        "pageSize": page_size,
        "orderBy": HOMEWORK_ORDER_BY,
        "order": HOMEWORK_ORDER,
    }
    response = session.post(HOMEWORK_API_URL, json=payload, timeout=20)
    return assert_api_ok(response)


def get_all_homeworks(session: requests.Session, classroom_id: str) -> list[dict]:
    records: list[dict] = []
    page_num = 1
    while True:
        data = fetch_homework_page(session, classroom_id, page_num, HOMEWORK_PAGE_SIZE)
        try:
            page_records = extract_homework_records(data)
        except RuntimeError:
            break
        records.extend(page_records)
        total = data.get("data", {}).get("total")
        if total is not None and len(records) >= int(total):
            break
        if len(page_records) < HOMEWORK_PAGE_SIZE:
            break
        page_num += 1
    return records


def get_homework_detail(session: requests.Session, homework_id: str) -> dict[str, Any]:
    response = session.post(
        HOMEWORK_DETAIL_API_URL,
        json={"action": ACTION_STUDENT, "homeworkId": homework_id},
        timeout=20,
    )
    return assert_api_ok(response)


def submit_answer_record(
    session: requests.Session, homework_id: str, question_id: str, mark: str
) -> dict[str, Any]:
    response = session.post(
        ANSWER_RECORD_API_URL,
        json={
            "action": ACTION_SUBMIT,
            "homeworkId": homework_id,
            "questionId": question_id,
            "options": [{"mark": mark, "content": ""}],
        },
        timeout=20,
    )
    return assert_api_ok(response)


def extract_homework_records(homework_data: dict) -> list[dict]:
    try:
        records = homework_data["data"]["records"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("作业列表响应结构不符合预期") from exc
    if not records:
        raise RuntimeError("当前课程没有作业")
    return records


def extract_questions(detail_data: dict) -> list[dict]:
    try:
        questions = detail_data["data"]["questions"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("作业详情响应结构不符合预期") from exc
    if not questions:
        raise RuntimeError("当前作业没有题目")
    return questions


def is_correct_answer(submit_data: dict) -> bool:
    try:
        score = submit_data["data"]["answerRecord"].get("answerRecordScore")
    except (KeyError, TypeError, AttributeError):
        return False
    return score is not None and score != 0


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", "", value).strip()


def find_latest_unprocessed_question(
    questions: list[dict], processed_question_ids: set[str]
) -> dict | None:
    for question in reversed(questions):
        question_id = question.get("questionId")
        if question_id and question_id not in processed_question_ids:
            return question
    return None