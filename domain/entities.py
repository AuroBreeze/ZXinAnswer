"""领域实体 — 纯数据结构，不依赖任何外部框架。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Course:
    id: str
    course_name: str
    teacher_name: str
    unfinished_count: int

    @classmethod
    def from_dict(cls, data: dict) -> Course:
        return cls(
            id=data.get("id", ""),
            course_name=data.get("courseName", ""),
            teacher_name=data.get("teacherName", ""),
            unfinished_count=data.get("unfinishedCount", 0),
        )


@dataclass
class Homework:
    id: str
    name: str
    answer_sheet_score: Any
    answer_progress: Any
    create_time: str | None
    deadline: str | None

    @classmethod
    def from_dict(cls, data: dict) -> Homework:
        return cls(
            id=data.get("id", ""),
            name=data.get("name") or data.get("id", "未知"),
            answer_sheet_score=data.get("answerSheetScore", "?"),
            answer_progress=data.get("answerProgress", "?"),
            create_time=data.get("createTime"),
            deadline=data.get("deadline"),
        )


@dataclass
class QuestionOption:
    mark: str
    content: str = ""


@dataclass
class Question:
    question_id: str
    question_index: Any
    content: str
    options: list[QuestionOption]
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Question:
        return cls(
            question_id=data.get("questionId", ""),
            question_index=data.get("questionIndex", "?"),
            content=data.get("content", ""),
            options=[
                QuestionOption(mark=o.get("mark", ""), content=o.get("content", ""))
                for o in data.get("options", [])
            ],
            raw=data,
        )


@dataclass
class AnswerResult:
    question_score: Any
    total_score: Any
    answer_progress: Any
    is_correct: bool
    raw: dict

    @classmethod
    def from_dict(cls, data: dict) -> AnswerResult:
        answer_record = data.get("data", {}).get("answerRecord", {})
        answer_sheet = data.get("data", {}).get("answerSheet", {})
        score = answer_record.get("answerRecordScore")
        return cls(
            question_score=score,
            total_score=answer_sheet.get("score", "?"),
            answer_progress=answer_sheet.get("answerProgress", "?"),
            is_correct=score is not None and score != 0,
            raw=data,
        )


@dataclass
class AnswerSummary:
    question_index: Any
    mark: str | None
    is_correct: bool