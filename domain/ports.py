"""端口（接口） — use_cases 依赖这些抽象，adapters 负责实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

import requests

from domain.entities import AnswerResult, AnswerSummary, Course, Homework, Question


class AuthPort(ABC):
    @abstractmethod
    def login_password(self, session: requests.Session, username: str, password: str) -> dict[str, Any]: ...

    @abstractmethod
    def login_wechat(self, session: requests.Session) -> bool: ...

    @abstractmethod
    def is_session_alive(self, session: requests.Session) -> bool: ...


class HomeworkPort(ABC):
    @abstractmethod
    def get_courses(self, session: requests.Session) -> list[Course]: ...

    @abstractmethod
    def get_homeworks(self, session: requests.Session, classroom_id: str) -> list[Homework]: ...

    @abstractmethod
    def get_homework_detail(self, session: requests.Session, homework_id: str) -> list[Question]: ...

    @abstractmethod
    def submit_answer(self, session: requests.Session, homework_id: str, question_id: str, mark: str) -> AnswerResult: ...


class PresenterPort(ABC):
    @abstractmethod
    def show_banner(self) -> None: ...

    @abstractmethod
    def info(self, message: str) -> None: ...

    @abstractmethod
    def success(self, message: str) -> None: ...

    @abstractmethod
    def warning(self, message: str) -> None: ...

    @abstractmethod
    def error(self, message: str) -> None: ...

    @abstractmethod
    def select_item(
        self,
        items: list[dict],
        columns: list[tuple[str, Callable[[dict], object]]],
        prompt: str,
        allow_back: bool = False,
    ) -> dict | None: ...

    @abstractmethod
    def show_question(self, question: Question, index: int, total: int) -> None: ...

    @abstractmethod
    def show_answer_attempt(self, attempt: int, total: int, mark: str, result: AnswerResult) -> None: ...

    @abstractmethod
    def show_answer_result(self, mark: str | None) -> None: ...

    @abstractmethod
    def show_summary(self, results: list[AnswerSummary]) -> None: ...

    @abstractmethod
    def prompt(self, message: str, password: bool = False) -> str: ...

    @abstractmethod
    def show_new_question(self, question: Question) -> None: ...


class QRCodePort(ABC):
    @abstractmethod
    def generate_ascii(self, url: str) -> None: ...

    @abstractmethod
    def save_png(self, url: str, filepath: str) -> None: ...


class CookiePort(ABC):
    @abstractmethod
    def create_session(self, filepath: str) -> requests.Session: ...

    @abstractmethod
    def save(self, session: requests.Session, filepath: str) -> None: ...

    @abstractmethod
    def clear(self, session: requests.Session, filepath: str) -> None: ...