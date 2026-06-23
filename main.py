"""UI & 入口：显示、交互、模式编排。"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, RuntimeError):
    pass

from auth import (
    ApiError,
    COOKIE_FILE,
    console,
    is_session_alive,
    load_credentials,
    login,
    make_session,
    wechat_qrcode_login,
)
from homework import (
    extract_questions,
    find_latest_unprocessed_question,
    get_all_homeworks,
    get_classroom_data,
    get_homework_detail,
    is_correct_answer,
    strip_html,
    submit_answer_record,
)

POLL_SECONDS = 5


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


# ---------- answering ----------

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


# ---------- login orchestration ----------

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