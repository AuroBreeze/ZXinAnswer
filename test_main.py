import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests
from rich.text import Text

from adapters.auth_api import assert_api_ok
from adapters.homework_api import HomeworkApiAdapter
from adapters.presenter import ConsolePresenter, _deadline_cell, _format_time, _parse_iso, _strip_html
from domain.entities import AnswerResult, Course, Homework, Question, QuestionOption
from domain.exceptions import ApiError, AuthenticationError, ExitRequested, HomeworkError
from use_cases.answer import AnswerUseCase
from use_cases.homework import HomeworkUseCase
from use_cases.login import LoginUseCase
from use_cases.wait import WaitLatestUseCase


def _resp(body: dict | str, status: int = 200) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
    return r


# ===== domain.entities =====

class TestCourse:
    def test_from_dict(self):
        c = Course.from_dict({"id": "1", "courseName": "OS", "teacherName": "Z", "unfinishedCount": 3})
        assert c.id == "1"
        assert c.course_name == "OS"
        assert c.teacher_name == "Z"
        assert c.unfinished_count == 3

    def test_from_dict_defaults(self):
        c = Course.from_dict({})
        assert c.id == ""
        assert c.course_name == ""
        assert c.unfinished_count == 0


class TestHomework:
    def test_from_dict(self):
        h = Homework.from_dict({"id": "h1", "name": "HW1", "answerSheetScore": 80, "answerProgress": "100", "createTime": "2026-06-01", "deadline": "2026-06-10"})
        assert h.id == "h1"
        assert h.name == "HW1"
        assert h.answer_sheet_score == 80
        assert h.answer_progress == "100"

    def test_from_dict_fallback_name(self):
        h = Homework.from_dict({"id": "h2"})
        assert h.name == "h2"


class TestQuestion:
    def test_from_dict(self):
        q = Question.from_dict({"questionId": "q1", "questionIndex": 3, "content": "<b>x</b>", "options": [{"mark": "A"}, {"mark": "B"}]})
        assert q.question_id == "q1"
        assert q.question_index == 3
        assert len(q.options) == 2
        assert q.options[0].mark == "A"

    def test_from_dict_defaults(self):
        q = Question.from_dict({})
        assert q.question_id == ""
        assert q.question_index == "?"
        assert q.options == []


class TestAnswerResult:
    def test_correct(self):
        r = AnswerResult.from_dict({"data": {"answerRecord": {"answerRecordScore": 5}, "answerSheet": {"score": 10, "answerProgress": 50}}})
        assert r.is_correct is True
        assert r.question_score == 5
        assert r.total_score == 10

    def test_zero_score(self):
        r = AnswerResult.from_dict({"data": {"answerRecord": {"answerRecordScore": 0}, "answerSheet": {}}})
        assert r.is_correct is False

    def test_none_score(self):
        r = AnswerResult.from_dict({"data": {"answerRecord": {"answerRecordScore": None}, "answerSheet": {}}})
        assert r.is_correct is False

    def test_missing_record(self):
        r = AnswerResult.from_dict({"data": {}})
        assert r.is_correct is False


# ===== adapters.auth_api.assert_api_ok =====

class TestAssertApiOk:
    def test_code_zero(self):
        assert assert_api_ok(_resp({"code": 0, "data": {}, "msg": "ok"}))["code"] == 0

    def test_code_200(self):
        assert assert_api_ok(_resp({"code": 200, "data": {}}))["code"] == 200

    def test_success_true(self):
        assert assert_api_ok(_resp({"success": True, "data": {}}))["success"] is True

    def test_code_nonzero_raises(self):
        with pytest.raises(ApiError, match="密码错误"):
            assert_api_ok(_resp({"code": 1, "msg": "密码错误"}))

    def test_success_false_raises(self):
        with pytest.raises(ApiError, match="未登录"):
            assert_api_ok(_resp({"success": False, "msg": "未登录"}))

    def test_http_error_raises(self):
        with pytest.raises(requests.HTTPError):
            assert_api_ok(_resp("not found", status=404))

    def test_invalid_json(self):
        with pytest.raises(ApiError, match="不是合法 JSON"):
            assert_api_ok(_resp("not json"))

    def test_non_object(self):
        with pytest.raises(ApiError, match="顶层不是对象"):
            assert_api_ok(_resp("[1,2,3]"))

    def test_code_string_zero(self):
        assert assert_api_ok(_resp({"code": "0", "data": {}}))["code"] == "0"

    def test_message_field(self):
        with pytest.raises(ApiError, match="用户名或密码错误"):
            assert_api_ok(_resp({"code": 401, "message": "用户名或密码错误"}))


# ===== adapters.presenter =====

class TestStripHtml:
    def test_strips(self):
        assert _strip_html("<p>hi</p>") == "hi"

    def test_nested(self):
        assert _strip_html("<div><b>x</b></div>") == "x"

    def test_none(self):
        assert _strip_html(None) == ""

    def test_empty(self):
        assert _strip_html("") == ""


class TestParseIso:
    def test_normal(self):
        dt = _parse_iso("2026-06-18T12:51:40.000Z")
        assert dt is not None and dt.year == 2026

    def test_none(self):
        assert _parse_iso(None) is None

    def test_invalid(self):
        assert _parse_iso("bad") is None


class TestFormatTime:
    def test_normal(self):
        assert "06-18" in _format_time("2026-06-18T12:51:40.000Z")

    def test_none(self):
        assert _format_time(None) == "?"

    def test_invalid(self):
        assert _format_time("bad") == "?"


class TestDeadlineCell:
    def test_no_deadline(self):
        cell = _deadline_cell({})
        assert "无截止" in cell.plain

    def test_past(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        cell = _deadline_cell({"deadline": past})
        assert "已截止" in cell.plain
        assert "red" in str(cell.style)

    def test_within_1h(self):
        soon = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        cell = _deadline_cell({"deadline": soon})
        assert "即将截止" in cell.plain
        assert "red" in str(cell.style)

    def test_within_24h(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        cell = _deadline_cell({"deadline": future})
        assert "h后" in cell.plain
        assert "yellow" in str(cell.style)

    def test_far(self):
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        cell = _deadline_cell({"deadline": future})
        assert "green" in str(cell.style)


# ===== HomeworkApiAdapter =====

class TestHomeworkApiAdapter:
    def test_get_courses(self, monkeypatch):
        raw = {"code": 0, "data": [{"id": "c1", "courseName": "OS", "teacherName": "Z", "unfinishedCount": 2}]}
        session = MagicMock()
        session.post.return_value = _resp(raw)
        adapter = HomeworkApiAdapter()
        courses = adapter.get_courses(session)
        assert len(courses) == 1
        assert courses[0].id == "c1"
        assert courses[0].course_name == "OS"

    def test_get_courses_empty(self, monkeypatch):
        session = MagicMock()
        session.post.return_value = _resp({"code": 0, "data": []})
        adapter = HomeworkApiAdapter()
        assert adapter.get_courses(session) == []

    def test_get_homework_detail(self, monkeypatch):
        raw = {"code": 0, "data": {"questions": [{"questionId": "q1", "questionIndex": 1, "content": "x", "options": []}]}}
        session = MagicMock()
        session.post.return_value = _resp(raw)
        adapter = HomeworkApiAdapter()
        questions = adapter.get_homework_detail(session, "h1")
        assert len(questions) == 1
        assert questions[0].question_id == "q1"

    def test_submit_answer(self, monkeypatch):
        raw = {"code": 0, "data": {"answerRecord": {"answerRecordScore": 5}, "answerSheet": {"score": 10, "answerProgress": 50}}}
        session = MagicMock()
        session.post.return_value = _resp(raw)
        adapter = HomeworkApiAdapter()
        result = adapter.submit_answer(session, "h1", "q1", "A")
        assert result.is_correct is True
        assert result.question_score == 5

    def test_get_homework_detail_no_questions(self, monkeypatch):
        raw = {"code": 0, "data": {"questions": []}}
        session = MagicMock()
        session.post.return_value = _resp(raw)
        adapter = HomeworkApiAdapter()
        with pytest.raises(HomeworkError, match="没有题目"):
            adapter.get_homework_detail(session, "h1")


# ===== use_cases.wait.WaitLatestUseCase =====

class TestFindLatestUnprocessed:
    def test_returns_last(self):
        qs = [Question("a", 1, "", []), Question("b", 2, "", []), Question("c", 3, "", [])]
        result = WaitLatestUseCase._find_latest_unprocessed(qs, {"a", "b"})
        assert result.question_id == "c"

    def test_all_processed(self):
        qs = [Question("a", 1, "", []), Question("b", 2, "", [])]
        assert WaitLatestUseCase._find_latest_unprocessed(qs, {"a", "b"}) is None

    def test_empty(self):
        assert WaitLatestUseCase._find_latest_unprocessed([], set()) is None

    def test_skips_empty_id(self):
        qs = [Question("", 1, "", []), Question("x", 2, "", [])]
        result = WaitLatestUseCase._find_latest_unprocessed(qs, set())
        assert result.question_id == "x"


# ===== use_cases.answer.AnswerUseCase =====

class TestAnswerUseCase:
    def test_answer_all(self, monkeypatch):
        api = MagicMock()
        api.submit_answer.side_effect = [
            AnswerResult(0, 0, 0, False, {}),
            AnswerResult(5, 10, 50, True, {}),
        ]
        presenter = MagicMock()
        uc = AnswerUseCase(api, presenter)
        question = Question("q1", 1, "content", [QuestionOption("A"), QuestionOption("B")])
        results = uc.answer_all(MagicMock(), "h1", [question])
        assert len(results) == 1
        assert results[0]["mark"] == "B"
        assert results[0]["is_correct"] is True


# ===== use_cases.login.LoginUseCase =====

class TestLoginUseCase:
    def test_skips_when_alive(self, monkeypatch):
        api = MagicMock()
        api.is_session_alive.return_value = True
        presenter = MagicMock()
        uc = LoginUseCase(api, MagicMock(), presenter)
        uc.ensure_logged_in(MagicMock(), "u", "p")
        api.login_password.assert_not_called()
        api.login_wechat.assert_not_called()

    def test_password_login(self, monkeypatch):
        api = MagicMock()
        api.is_session_alive.return_value = False
        presenter = MagicMock()
        presenter.select_item.return_value = {"id": "2", "name": "账号密码"}
        uc = LoginUseCase(api, MagicMock(), presenter)
        uc.ensure_logged_in(MagicMock(), "u", "p")
        api.login_password.assert_called_once()

    def test_password_no_credentials(self, monkeypatch):
        api = MagicMock()
        api.is_session_alive.return_value = False
        presenter = MagicMock()
        presenter.select_item.return_value = {"id": "2", "name": "账号密码"}
        uc = LoginUseCase(api, MagicMock(), presenter)
        with pytest.raises(AuthenticationError, match="环境变量"):
            uc.ensure_logged_in(MagicMock(), None, None)

    def test_wechat_login(self, monkeypatch):
        api = MagicMock()
        api.is_session_alive.return_value = False
        api.login_wechat.return_value = True
        presenter = MagicMock()
        presenter.select_item.return_value = {"id": "1", "name": "微信扫码"}
        uc = LoginUseCase(api, MagicMock(), presenter)
        uc.ensure_logged_in(MagicMock())
        api.login_wechat.assert_called_once()

    def test_wechat_login_fails(self, monkeypatch):
        api = MagicMock()
        api.is_session_alive.return_value = False
        api.login_wechat.return_value = False
        presenter = MagicMock()
        presenter.select_item.return_value = {"id": "1", "name": "微信扫码"}
        uc = LoginUseCase(api, MagicMock(), presenter)
        with pytest.raises(AuthenticationError, match="扫码登录失败"):
            uc.ensure_logged_in(MagicMock())


# ===== ConsolePresenter.select_item: q 退出 =====

class TestSelectItemExit:
    def test_q_raises_exit_requested(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["q"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        items = [{"id": "1"}, {"id": "2"}]
        with pytest.raises(ExitRequested):
            presenter.select_item(items, [("id", lambda x: x["id"])], "prompt", allow_back=True)

    def test_q_raises_without_back(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["q"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        with pytest.raises(ExitRequested):
            presenter.select_item([{"id": "1"}], [("id", lambda x: x["id"])], "prompt")

    def test_q_uppercase_raises(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["Q"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        with pytest.raises(ExitRequested):
            presenter.select_item([{"id": "1"}], [("id", lambda x: x["id"])], "prompt")

    def test_q_then_valid_returns_item(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["x", "1"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        items = [{"id": "1"}, {"id": "2"}]
        result = presenter.select_item(items, [("id", lambda x: x["id"])], "prompt")
        assert result == {"id": "1"}

    def test_back_returns_none_with_q_available(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["b"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        items = [{"id": "1"}]
        result = presenter.select_item(items, [("id", lambda x: x["id"])], "prompt", allow_back=True)
        assert result is None