import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

# 确保终端能输出 Unicode（◌"▀▄█"等二维码半块字符）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, RuntimeError):
    pass
from http.cookiejar import MozillaCookieJar
from typing import Any, Callable

import qrcode
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


AUTH_HOST = "https://auth.z-xin.net"
LOGIN_URL = f"{AUTH_HOST}/api/portal/auth/login"
WECHAT_QRCODE_URL = f"{AUTH_HOST}/api/portal/wechat/qrcode"
WECHAT_LOGIN_CHECK_URL = f"{AUTH_HOST}/api/portal/wechat/login-check"
USER_SESSION_URL = "https://stu.z-xin.net/api/portal/user/session"
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
QR_IMAGE_FILE = "zxin_qrcode.png"
POLL_SECONDS = 5
SCAN_POLL_SECONDS = 3


class ApiError(RuntimeError):
    pass


class ApiError(RuntimeError):
    pass


# ---------- credentials & session ----------

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
        console.print(f"[green]✓[/green] 已加载 cookie: {cookie_file}")
    except FileNotFoundError:
        console.print("[yellow]→[/yellow] 未找到本地 cookie，将重新登录")

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


# ---------- API & business logic ----------

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
        msg = data.get("msg") or data.get("message")
        raise ApiError(f"业务错误 code={code!r} msg={msg!r}")
    if success is False:
        msg = data.get("msg") or data.get("message")
        raise ApiError(f"业务失败 success=False msg={msg!r}")
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


def _print_qr_ascii(url: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    # 合并两行为一行：用半块字符 ▀▄█ 将高度减半，宽度也用单字符减半
    # 上黑下黑=█  上黑下白=▀  上白下黑=▄  上白下白=空格
    for y in range(0, len(matrix), 2):
        line = []
        for x in range(len(matrix[0])):
            top = matrix[y][x]
            bot = matrix[y + 1][x] if y + 1 < len(matrix) else False
            if top and bot:
                line.append("█")
            elif top:
                line.append("▀")
            elif bot:
                line.append("▄")
            else:
                line.append(" ")
        console.print("".join(line), end="")
        console.print()


def wechat_qrcode_login(session: requests.Session) -> bool:
    scene_id = str(uuid.uuid4())
    console.print(f"[cyan]→[/cyan] 生成登录会话: {scene_id[:8]}...")

    headers = {"Referer": f"{AUTH_HOST}/login"}
    resp = session.get(f"{WECHAT_QRCODE_URL}/{scene_id}", headers=headers, timeout=15)
    data = assert_api_ok(resp)
    qr_data = data["data"]
    qr_url = qr_data.get("url") or qr_data.get("ticket") or ""
    expire_seconds = qr_data.get("expire_seconds", 180)
    if not qr_url:
        raise ApiError(f"二维码响应缺少 url 字段: {data!r}")

    try:
        img = qrcode.make(qr_url)
        img.save(QR_IMAGE_FILE)
    except Exception as exc:
        console.print(f"[yellow]⚠ 保存 PNG 失败: {exc}[/yellow]")

    console.print(Panel.fit(
        "微信扫码登录\n请用微信扫描下方二维码（或打开图片/链接）",
        border_style="green",
    ))
    _print_qr_ascii(qr_url)
    console.print(f"[dim]PNG: {QR_IMAGE_FILE}[/dim]")
    console.print(f"[dim]URL: {qr_url}[/dim]")
    console.print(f"[dim]有效期: {expire_seconds}s[/dim]\n")

    console.print("[cyan]等待扫码...[/cyan]")
    start = time.time()
    scanned = False
    while True:
        if time.time() - start > expire_seconds:
            console.print("[red]✗ 二维码已过期，请重新登录[/red]")
            return False
        try:
            resp = session.get(
                WECHAT_LOGIN_CHECK_URL, params={"scene": scene_id}, headers=headers, timeout=15
            )
            data = resp.json()
            code = data.get("code")
            if code == 200:
                console.print("[green]✓ 登录成功[/green]")
                session.cookies.save(ignore_discard=True, ignore_expires=True)
                console.print(f"[green]✓ cookie 已保存到 {COOKIE_FILE}[/green]")
                return True
            if code == 202:
                if not scanned:
                    console.print("\n[yellow]已扫码，请在手机上确认...[/yellow]")
                    scanned = True
            else:
                console.print(".", end="")
                sys.stdout.flush()
        except requests.RequestException as exc:
            console.print(f"\n[yellow]⚠ 轮询异常: {exc}[/yellow]")
        time.sleep(SCAN_POLL_SECONDS)
    return False


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
    session: requests.Session, username: str | None, password: str | None
) -> None:
    if is_session_alive(session):
        console.print("[green]✓[/green] cookie 有效，跳过登录")
        return
    console.print("[yellow]→[/yellow] cookie 失效，请选择登录方式")
    choice = select_item(
        [
            {"id": "1", "name": "微信扫码"},
            {"id": "2", "name": "账号密码"},
        ],
        [("方式", lambda item: item["name"])],
        "[bold cyan]请选择登录方式序号: [/bold cyan]",
    )
    if choice["id"] == "1":
        if not wechat_qrcode_login(session):
            raise RuntimeError("扫码登录失败")
    else:
        if not username or not password:
            username, password = load_credentials()
        login(session, username, password)
        console.print(f"[green]✓[/green] 登录成功，cookie 已保存到 {COOKIE_FILE}")


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


# ---------- display helpers ----------

def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_time(value: str | None) -> str:
    dt = parse_iso(value)
    if dt is None:
        return "?"
    local = dt.astimezone()
    return local.strftime("%m-%d %H:%M")


def deadline_cell(homework: dict) -> Text:
    deadline = parse_iso(homework.get("deadline"))
    if deadline is None:
        return Text("无截止", style="dim")
    now = datetime.now(timezone.utc)
    if deadline <= now:
        return Text(f"{format_time(homework.get('deadline'))} 已截止", style="bold red")
    remaining = deadline - now
    if remaining <= timedelta(hours=1):
        return Text(f"{format_time(homework.get('deadline'))} 即将截止", style="bold red")
    if remaining <= timedelta(hours=24):
        return Text(f"{format_time(homework.get('deadline'))} {remaining.seconds // 3600}h后", style="yellow")
    return Text(format_time(homework.get("deadline")), style="green")


def question_label(question: dict) -> str:
    marks = "/".join(option.get("mark", "") for option in question.get("options", []))
    content = strip_html(question.get("content"))
    return f"第{question.get('questionIndex', '?')}题 {content} [{marks}]"


def progress_text(data: dict) -> str:
    answer_record = data.get("data", {}).get("answerRecord", {})
    answer_sheet = data.get("data", {}).get("answerSheet", {})
    return (
        f"本题 {answer_record.get('answerRecordScore', '?')} · "
        f"总分 {answer_sheet.get('score', '?')} · "
        f"作答 {answer_sheet.get('answerProgress', '?')}%"
    )


def select_item(
    items: list[dict],
    columns: list[tuple[str, Callable[[dict], object]]],
    prompt: str,
    allow_back: bool = False,
) -> dict | None:
    back_hint = "  [dim](b 返回)[/dim]" if allow_back else ""
    table = Table(show_header=True, header_style="bold cyan", border_style="dim", expand=False)
    table.add_column("#", style="cyan", justify="right", width=3)
    for header, _ in columns:
        table.add_column(header)
    for index, item in enumerate(items, start=1):
        row = [str(index)] + [col[1](item) for col in columns]
        table.add_row(*row)
    console.print(table)
    while True:
        value = console.input(prompt + back_hint + " ").strip()
        if allow_back and value.lower() in ("b", "0"):
            return None
        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(items):
                return items[index - 1]
        console.print("[red]请输入有效序号[/red]")


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
        correct = is_correct_answer(data)
        icon = "[green]✓[/green]" if correct else "[red]·[/red]"
        console.print(
            f"  [dim]尝试 {index}/{len(options)}[/dim] → [bold]{mark}[/bold] "
            f"{icon} [dim]{progress_text(data)}[/dim]"
        )
        if correct:
            return mark, data
    return None, last_data


def answer_all_questions(
    session: requests.Session, homework_id: str, questions: list[dict]
) -> list[dict]:
    results = []
    total = len(questions)
    for index, question in enumerate(questions, start=1):
        qidx = question.get("questionIndex", index)
        content = strip_html(question.get("content"))
        marks = "/".join(o.get("mark", "") for o in question.get("options", []))
        console.print()
        console.print(Panel.fit(
            f"[bold]第 {qidx} 题[/bold]  {content}  [dim][{marks}][/dim]"
            f"  [dim]({index}/{total})[/dim]",
            border_style="cyan",
        ))
        mark, data = submit_until_correct(session, homework_id, question)
        if mark:
            console.print(f"  [green]✓ 正确答案: [bold]{mark}[/bold][/green]")
        else:
            console.print(f"  [red]✗ 未找到正确答案[/red]")
        results.append({"question": question, "mark": mark, "data": data})
    return results


def print_summary(results: list[dict]) -> None:
    table = Table(
        title="[bold]答题汇总[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("题号", style="cyan", justify="right")
    table.add_column("答案", style="bold")
    table.add_column("状态")
    success_count = 0
    for result in results:
        question = result["question"]
        qidx = str(question.get("questionIndex", "?"))
        if result["mark"]:
            success_count += 1
            table.add_row(qidx, result["mark"], "[green]✓ 正确[/green]")
        else:
            table.add_row(qidx, "-", "[red]✗ 未找到[/red]")
    console.print()
    console.print(table)
    total = len(results)
    if total == 0:
        return
    if success_count == total:
        color = "green"
    elif success_count > 0:
        color = "yellow"
    else:
        color = "red"
    console.print(
        f"[{color}]总计：成功 {success_count} / {total}，"
        f"失败 {total - success_count}[/{color}]"
    )


# ---------- modes ----------

def run_select_question_mode(session: requests.Session, classroom_id: str) -> dict | None:
    homeworks = get_all_homeworks(session, classroom_id)
    if not homeworks:
        console.print("[yellow]⚠ 当前课程没有作业[/yellow]")
        return None
    console.print("\n[bold]作业列表[/bold]")
    homework = select_item(
        homeworks,
        [
            ("作业名", lambda h: h.get("name") or h.get("id", "未知")),
            ("得分", lambda h: str(h.get("answerSheetScore", "?"))),
            ("作答", lambda h: f"{h.get('answerProgress', '?')}%"),
            ("创建时间", lambda h: format_time(h.get("createTime"))),
            ("截止时间", deadline_cell),
        ],
        "[bold cyan]请选择作业序号: [/bold cyan]",
        allow_back=True,
    )
    if homework is None:
        return None
    detail_data = get_homework_detail(session, homework["id"])
    questions = extract_questions(detail_data)
    results = answer_all_questions(session, homework["id"], questions)
    print_summary(results)
    return homework


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
                qidx = question.get("questionIndex", "?")
                content = strip_html(question.get("content"))
                console.print(f"\n[bold cyan]▶ 新题[/bold cyan] 第{qidx}题 {content}")
                mark, data = submit_until_correct(session, homework_id, question)
                processed_question_ids.add(question["questionId"])
                if mark:
                    console.print(f"  [green]✓ 正确答案: [bold]{mark}[/bold][/green]")
                else:
                    console.print(f"  [red]✗ 未找到正确答案[/red]")
            else:
                console.print("[dim]暂无新题，继续等待...[/dim]")
        except requests.RequestException as exc:
            console.print(f"[yellow]⚠ 网络异常，继续轮询: {exc}[/yellow]")
        except RuntimeError as exc:
            console.print(f"[yellow]⚠ 等待中: {exc}[/yellow]")
        time.sleep(poll_seconds)


def select_mode() -> dict | None:
    return select_item(
        [{"id": "1", "name": "选择作业自动答完"}, {"id": "2", "name": "等待最新题目"}],
        [("模式", lambda item: item["name"])],
        "[bold cyan]请选择模式序号: [/bold cyan]",
        allow_back=True,
    )


def print_banner() -> None:
    console.print(Panel(
        "[bold cyan]z-xin 作业助手[/bold cyan]\n[dim]自动答题 · 课程作业 · 实时轮询[/dim]",
        border_style="cyan",
        expand=False,
    ))


def main() -> int:
    print_banner()
    try:
        username = os.environ.get("ZXIN_USERNAME")
        password = os.environ.get("ZXIN_PASSWORD")
        session = make_session()
        ensure_logged_in(session, username, password)

        while True:
            courses = get_classroom_data(session)
            if not courses:
                raise RuntimeError("没有可选择的课程")
            console.print("\n[bold]课程列表[/bold]")
            course = select_item(
                courses,
                [
                    ("课程", lambda c: c.get("courseName", "")),
                    ("教师", lambda c: c.get("teacherName", "")),
                    ("未完成", lambda c: str(c.get("unfinishedCount", 0))),
                ],
                "[bold cyan]请选择课程序号: [/bold cyan]",
            )

            while True:
                mode = select_mode()
                if mode is None:
                    break
                if mode["id"] == "1":
                    result = run_select_question_mode(session, course["id"])
                    if result is None:
                        continue
                    while True:
                        again = console.input(
                            "[bold cyan]再答一份? (Enter 继续, b 返回模式选择, q 退出): [/bold cyan]"
                        ).strip().lower()
                        if again == "q":
                            return 0
                        if again == "b":
                            break
                        result = run_select_question_mode(session, course["id"])
                        if result is None:
                            break
                    if again == "q":
                        return 0
                    continue
                else:
                    run_wait_latest_mode(session, course["id"])
                    return 0
    except KeyboardInterrupt:
        console.print("\n[dim]已退出[/dim]")
        return 0
    except requests.RequestException as exc:
        console.print(f"[red]✗ 请求失败: {exc}[/red]")
        return 1
    except (RuntimeError, ApiError) as exc:
        console.print(f"[red]✗ {exc}[/red]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
