"""控制台呈现器 — 实现 PresenterPort，使用 rich 渲染终端 UI。"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from domain.entities import AnswerResult, Question
from domain.exceptions import ExitRequested

console = Console()


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", "", value).strip()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_time(value: str | None) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return "?"
    return dt.astimezone().strftime("%m-%d %H:%M")


def _deadline_cell(homework_dict: dict) -> Text:
    deadline = _parse_iso(homework_dict.get("deadline"))
    if deadline is None:
        return Text("无截止", style="dim")
    now = datetime.now(timezone.utc)
    if deadline <= now:
        return Text(f"{_format_time(homework_dict.get('deadline'))} 已截止", style="bold red")
    remaining = deadline - now
    if remaining <= timedelta(hours=1):
        return Text(f"{_format_time(homework_dict.get('deadline'))} 即将截止", style="bold red")
    if remaining <= timedelta(hours=24):
        return Text(f"{_format_time(homework_dict.get('deadline'))} {remaining.seconds // 3600}h后", style="yellow")
    return Text(_format_time(homework_dict.get("deadline")), style="green")


def _progress_text(result: AnswerResult) -> str:
    return (
        f"本题 {result.question_score} · "
        f"总分 {result.total_score} · "
        f"作答 {result.answer_progress}%"
    )


class ConsolePresenter:
    """实现 PresenterPort 的终端呈现器。"""

    def show_banner(self) -> None:
        console.print(Panel(
            "[bold cyan]z-xin 作业助手[/bold cyan]\n[dim]自动答题 · 课程作业 · 实时轮询[/dim]",
            border_style="cyan",
            expand=False,
        ))

    def info(self, message: str) -> None:
        console.print(f"[cyan]→[/cyan] {message}")

    def success(self, message: str) -> None:
        console.print(f"[green]✓[/green] {message}")

    def warning(self, message: str) -> None:
        console.print(f"[yellow]⚠[/yellow] {message}")

    def error(self, message: str) -> None:
        console.print(f"[red]✗[/red] {message}")

    def select_item(
        self,
        items: list[dict],
        columns: list[tuple[str, Callable[[dict], object]]],
        prompt: str,
        allow_back: bool = False,
    ) -> dict | None:
        hints = []
        if allow_back:
            hints.append("b 返回")
        hints.append("q 退出")
        hint_str = "  [dim](" + ", ".join(hints) + ")[/dim]"
        table = Table(show_header=True, header_style="bold cyan", border_style="dim", expand=False)
        table.add_column("#", style="cyan", justify="right", width=3)
        for header, _ in columns:
            table.add_column(header)
        for index, item in enumerate(items, start=1):
            row = [str(index)] + [col[1](item) for col in columns]
            table.add_row(*row)
        console.print(table)
        while True:
            value = console.input(prompt + hint_str + " ").strip()
            if value.lower() == "q":
                raise ExitRequested()
            if allow_back and value.lower() in ("b", "0"):
                return None
            if value.isdigit():
                index = int(value)
                if 1 <= index <= len(items):
                    return items[index - 1]
            console.print("[red]请输入有效序号[/red]")

    def show_question(self, question: Question, index: int, total: int) -> None:
        qidx = question.question_index
        content = _strip_html(question.content)
        marks = "/".join(o.mark for o in question.options)
        console.print()
        console.print(Panel.fit(
            f"[bold]第 {qidx} 题[/bold]  {content}  [dim][{marks}][/dim]"
            f"  [dim]({index}/{total})[/dim]",
            border_style="cyan",
        ))

    def show_answer_attempt(self, attempt: int, total: int, mark: str, result: AnswerResult) -> None:
        icon = "[green]✓[/green]" if result.is_correct else "[red]·[/red]"
        console.print(
            f"  [dim]尝试 {attempt}/{total}[/dim] → [bold]{mark}[/bold] "
            f"{icon} [dim]{_progress_text(result)}[/dim]"
        )

    def show_answer_result(self, mark: str | None) -> None:
        if mark:
            console.print(f"  [green]✓ 正确答案: [bold]{mark}[/bold][/green]")
        else:
            console.print(f"  [red]✗ 未找到正确答案[/red]")

    def show_summary(self, results: list[dict]) -> None:
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
            qidx = str(result.get("question_index", "?"))
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

    def prompt(self, message: str) -> str:
        return console.input(message).strip()

    def show_new_question(self, question: Question) -> None:
        qidx = question.question_index
        content = _strip_html(question.content)
        console.print(f"\n[bold cyan]▶ 新题[/bold cyan] 第{qidx}题 {content}")