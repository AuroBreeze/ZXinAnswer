import json
import os
import re
import sys
import time
from http.cookiejar import MozillaCookieJar
from typing import Any

import requests


LOGIN_URL = "https://auth.z-xin.net/api/portal/auth/login"
CLASSROOM_API_URL = "https://stu.z-xin.net/api/classroom"
HOMEWORK_API_URL = "https://stu.z-xin.net/api/homework"
HOMEWORK_DETAIL_API_URL = "https://stu.z-xin.net/api/homework/detail"
ANSWER_RECORD_API_URL = "https://stu.z-xin.net/api/answer-record"

ACTION_STUDENT_GET = "studentGet"
ACTION_STUDENT_PAGE = "studentPage"
ACTION_STUDENT = "student"
ACTION_SUBMIT = "submit"

CLASSROOM_PAYLOAD = {"action": ACTION_STUDENT_GET, "termId": "2015701567531511810"}
HOMEWORK_PAGE_SIZE = 20
HOMEWORK_ORDER_BY = "createTime"
HOMEWORK_ORDER = "desc"

COOKIE_FILE = "cookies.txt"
POLL_SECONDS = 5


class ApiError(RuntimeError):
    pass


def load_credentials() -> tuple[str, str]:
    username = os.environ.get("ZXIN_USERNAME")
    password = os.environ.get("ZXIN_PASSWORD")
    if not username or not password:
        raise RuntimeError("请先设置环境变量 ZXIN_USERNAME 和 ZXIN_PASSWORD")
    return username, password


def make_session(cookie_file: str = COOKIE_FILE) -> requests.Session:
    session = requests.Session()
    session.cookies = MozillaCookieJar(cookie_file)
    try:
        session.cookies.load(ignore_discard=True, ignore_expires=True)
        print(f"已加载 cookie: {cookie_file}")
    except FileNotFoundError:
        print("未找到本地 cookie，将重新登录")

    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://stu.z-xin.net",
            "Referer": "https://stu.z-xin.net/",
        }
    )
    return session


def assert_api_ok(response: requests.Response) -> dict[str, Any]:
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        raise ApiError(f"响应不是合法 JSON: {exc} | body={response.text[:200]}") from exc

    if not isinstance(data, dict):
        raise ApiError(f"响应顶层不是对象: {data!r}")

    code = data.get("code")
    success = data.get("success")
    if code is not None and code not in (0, 200, "0", "200") and success is not True:
        raise ApiError(f"业务错误 code={code!r} msg={data.get('msg')!r}")
    if success is False:
        raise ApiError(f"业务失败 success=False msg={data.get('msg')!r}")
    return data


def login(session: requests.Session, username: str, password: str) -> dict[str, Any]:
    response = session.post(
        LOGIN_URL,
        json={"username": username, "password": password},
        timeout=20,
    )
    data = assert_api_ok(response)
    session.cookies.save(ignore_discard=True, ignore_expires=True)
    return data


def is_session_alive(session: requests.Session) -> bool:
    try:
        response = session.post(CLASSROOM_API_URL, json=CLASSROOM_PAYLOAD, timeout=20)
    except requests.RequestException:
        return False
    try:
        assert_api_ok(response)
    except (requests.RequestException, ApiError):
        return False
    return True


def ensure_logged_in(
    session: requests.Session, username: str, password: str
) -> None:
    if is_session_alive(session):
        print("cookie 仍有效，跳过登录")
        return
    print("cookie 失效，重新登录")
    login_data = login(session, username, password)
    print(f"登录响应: {json.dumps(login_data, ensure_ascii=False)[:300]}")
    print(f"cookie 已保存到: {COOKIE_FILE}")


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
        page_records = extract_homework_records(data)
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


def select_item(items: list[dict], label_func, prompt: str) -> dict:
    for index, item in enumerate(items, start=1):
        print(f"{index}. {label_func(item)}")
    while True:
        value = input(prompt).strip()
        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(items):
                return items[index - 1]
        print("请输入有效序号")


def submit_until_correct(
    session: requests.Session, homework_id: str, question: dict
) -> tuple[str | None, dict]:
    last_data: dict[str, Any] = {}
    question_id = question["questionId"]
    options = question.get("options", [])
    for index, option in enumerate(options, start=1):
        mark = option["mark"]
        data = submit_answer_record(session, homework_id, question_id, mark)
        last_data = data
        print(f"尝试 {index}/{len(options)}：{mark} | {answer_status_text(data)}")
        if is_correct_answer(data):
            return mark, data
    return None, last_data


def answer_all_questions(
    session: requests.Session, homework_id: str, questions: list[dict]
) -> list[dict]:
    results = []
    for index, question in enumerate(questions, start=1):
        print(f"开始作答 {index}/{len(questions)}：{question_label(question)}")
        mark, data = submit_until_correct(session, homework_id, question)
        if mark:
            print(f"第{question.get('questionIndex', index)}题正确答案: {mark}")
        else:
            print(f"第{question.get('questionIndex', index)}题未找到正确答案")
        print(final_answer_status_text(data))
        results.append({"question": question, "mark": mark, "data": data})
    return results


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", "", value).strip()


def course_label(course: dict) -> str:
    return (
        f"{course.get('courseName', '')} - {course.get('teacherName', '')} "
        f"(未完成: {course.get('unfinishedCount', '0')})"
    )


def homework_status_text(homework: dict) -> str:
    score = homework.get("answerSheetScore", "未知")
    answer_progress = homework.get("answerProgress", "未知")
    correct_progress = homework.get("correctProgress", "未知")
    return f"得分: {score} | 作答: {answer_progress}% | 正确: {correct_progress}%"


def homework_label(homework: dict) -> str:
    name = homework.get("name") or homework.get("id", "未知作业")
    return f"{name} | {homework_status_text(homework)}"


def answer_status_text(submit_data: dict) -> str:
    answer_record = submit_data.get("data", {}).get("answerRecord", {})
    answer_sheet = submit_data.get("data", {}).get("answerSheet", {})
    question_score = answer_record.get("answerRecordScore", "未知")
    sheet_score = answer_sheet.get("score", "未知")
    answer_progress = answer_sheet.get("answerProgress", "未知")
    correct_progress = answer_sheet.get("correctProgress", "未知")
    return (
        f"本题得分: {question_score} | 作业总分: {sheet_score} | "
        f"作答: {answer_progress}% | 正确: {correct_progress}%"
    )


def final_answer_status_text(submit_data: dict) -> str:
    return f"最终状态: {answer_status_text(submit_data)}"


def answer_summary_text(results: list[dict]) -> str:
    lines = ["答题汇总:"]
    success_count = 0
    for result in results:
        question = result["question"]
        mark = result["mark"]
        question_index = question.get("questionIndex", "?")
        if mark:
            success_count += 1
            answer_text = f"正确答案: {mark}"
        else:
            answer_text = "未找到正确答案"
        lines.append(
            f"第{question_index}题 | {answer_text} | {answer_status_text(result['data'])}"
        )
    lines.append(f"总计：成功 {success_count} / {len(results)}，失败 {len(results) - success_count}")
    return "\n".join(lines)


def question_label(question: dict) -> str:
    marks = "/".join(option.get("mark", "") for option in question.get("options", []))
    content = strip_html(question.get("content"))
    return f"第{question.get('questionIndex', '?')}题 {content} [{marks}]"


def find_latest_unprocessed_question(
    questions: list[dict], processed_question_ids: set[str]
) -> dict | None:
    for question in reversed(questions):
        question_id = question.get("questionId")
        if question_id and question_id not in processed_question_ids:
            return question
    return None


def run_select_question_mode(session: requests.Session, classroom_id: str) -> None:
    homeworks = get_all_homeworks(session, classroom_id)
    homework = select_item(homeworks, homework_label, "请选择作业序号: ")
    detail_data = get_homework_detail(session, homework["id"])
    questions = extract_questions(detail_data)
    results = answer_all_questions(session, homework["id"], questions)
    print(answer_summary_text(results))


def run_wait_latest_mode(
    session: requests.Session, classroom_id: str, poll_seconds: int = POLL_SECONDS
) -> None:
    processed_by_homework: dict[str, set[str]] = {}
    while True:
        try:
            homeworks = get_all_homeworks(session, classroom_id)
            homework = homeworks[0]
            homework_id = homework["id"]
            processed_question_ids = processed_by_homework.setdefault(homework_id, set())

            detail_data = get_homework_detail(session, homework_id)
            questions = extract_questions(detail_data)
            question = find_latest_unprocessed_question(questions, processed_question_ids)
            if question:
                mark, data = submit_until_correct(session, homework_id, question)
                processed_question_ids.add(question["questionId"])
                if mark:
                    print(f"最新题正确答案: {mark}")
                else:
                    print("最新题未找到正确答案")
                print(final_answer_status_text(data))
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print("暂无新题，继续等待")
        except requests.RequestException as exc:
            print(f"网络异常，继续轮询: {exc}")
        except RuntimeError as exc:
            print(f"等待中: {exc}")
        time.sleep(poll_seconds)


def select_mode() -> dict:
    return select_item(
        [{"id": "1", "name": "选择作业自动答完"}, {"id": "2", "name": "等待最新题目"}],
        lambda item: item["name"],
        "请选择模式序号: ",
    )


def main() -> int:
    try:
        username, password = load_credentials()
        session = make_session()
        ensure_logged_in(session, username, password)

        courses = get_classroom_data(session)
        if not courses:
            raise RuntimeError("没有可选择的课程")
        course = select_item(courses, course_label, "请选择课程序号: ")
        mode = select_mode()
        if mode["id"] == "1":
            run_select_question_mode(session, course["id"])
        else:
            run_wait_latest_mode(session, course["id"])
        return 0
    except requests.RequestException as exc:
        print(f"请求失败: {exc}", file=sys.stderr)
        return 1
    except (RuntimeError, ApiError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
