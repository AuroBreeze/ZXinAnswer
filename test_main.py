import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests
from rich.text import Text

import main
from main import (
    ApiError,
    assert_api_ok,
    deadline_cell,
    extract_homework_records,
    extract_questions,
    find_latest_unprocessed_question,
    format_time,
    is_correct_answer,
    parse_iso,
    progress_text,
    question_label,
    strip_html,
)


def _resp(body: dict | str, status: int = 200) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
    return r


class TestAssertApiOk:
    def test_code_zero_passes(self):
        r = _resp({"code": 0, "data": {"x": 1}, "msg": "ok"})
        assert assert_api_ok(r) == {"code": 0, "data": {"x": 1}, "msg": "ok"}

    def test_code_200_passes(self):
        r = _resp({"code": 200, "data": {}})
        assert assert_api_ok(r)["code"] == 200

    def test_success_true_passes(self):
        r = _resp({"success": True, "data": {}})
        assert assert_api_ok(r)["success"] is True

    def test_code_nonzero_raises(self):
        r = _resp({"code": 1, "msg": "密码错误"})
        with pytest.raises(ApiError, match="密码错误"):
            assert_api_ok(r)

    def test_success_false_raises(self):
        r = _resp({"success": False, "msg": "未登录"})
        with pytest.raises(ApiError, match="未登录"):
            assert_api_ok(r)

    def test_http_error_raises(self):
        r = _resp("not found", status=404)
        with pytest.raises(requests.HTTPError):
            assert_api_ok(r)

    def test_invalid_json_raises(self):
        r = _resp("not json at all")
        with pytest.raises(ApiError, match="不是合法 JSON"):
            assert_api_ok(r)

    def test_non_object_top_raises(self):
        r = _resp("[1,2,3]")
        with pytest.raises(ApiError, match="顶层不是对象"):
            assert_api_ok(r)

    def test_code_string_zero_passes(self):
        r = _resp({"code": "0", "data": {}})
        assert assert_api_ok(r)["code"] == "0"


class TestIsCorrectAnswer:
    def test_nonzero_score(self):
        assert is_correct_answer({"data": {"answerRecord": {"answerRecordScore": 5}}}) is True

    def test_zero_score(self):
        assert is_correct_answer({"data": {"answerRecord": {"answerRecordScore": 0}}}) is False

    def test_none_score(self):
        assert is_correct_answer({"data": {"answerRecord": {"answerRecordScore": None}}}) is False

    def test_missing_score(self):
        assert is_correct_answer({"data": {"answerRecord": {}}}) is False

    def test_missing_record(self):
        assert is_correct_answer({"data": {}}) is False

    def test_missing_data(self):
        assert is_correct_answer({}) is False


class TestStripHtml:
    def test_strips_tags(self):
        assert strip_html("<p>hello</p>") == "hello"

    def test_nested_tags(self):
        assert strip_html("<div><b>hi</b></div>") == "hi"

    def test_none(self):
        assert strip_html(None) == ""

    def test_empty(self):
        assert strip_html("") == ""

    def test_with_entities_kept(self):
        assert strip_html("<p>a &amp; b</p>") == "a &amp; b"


class TestExtractHomeworkRecords:
    def test_normal(self):
        data = {"data": {"records": [{"id": "1"}, {"id": "2"}]}}
        assert extract_homework_records(data) == [{"id": "1"}, {"id": "2"}]

    def test_empty_raises(self):
        with pytest.raises(RuntimeError, match="没有作业"):
            extract_homework_records({"data": {"records": []}})

    def test_missing_records_raises(self):
        with pytest.raises(RuntimeError, match="结构不符合预期"):
            extract_homework_records({"data": {}})

    def test_missing_data_raises(self):
        with pytest.raises(RuntimeError, match="结构不符合预期"):
            extract_homework_records({})


class TestExtractQuestions:
    def test_normal(self):
        data = {"data": {"questions": [{"questionId": "q1"}]}}
        assert extract_questions(data) == [{"questionId": "q1"}]

    def test_empty_raises(self):
        with pytest.raises(RuntimeError, match="没有题目"):
            extract_questions({"data": {"questions": []}})

    def test_missing_raises(self):
        with pytest.raises(RuntimeError, match="结构不符合预期"):
            extract_questions({"data": {}})


class TestFindLatestUnprocessedQuestion:
    def test_returns_last_unprocessed(self):
        qs = [
            {"questionId": "a"},
            {"questionId": "b"},
            {"questionId": "c"},
        ]
        result = find_latest_unprocessed_question(qs, {"a", "b"})
        assert result == {"questionId": "c"}

    def test_all_processed_returns_none(self):
        qs = [{"questionId": "a"}, {"questionId": "b"}]
        assert find_latest_unprocessed_question(qs, {"a", "b"}) is None

    def test_empty_returns_none(self):
        assert find_latest_unprocessed_question([], set()) is None

    def test_skips_missing_id(self):
        qs = [{"questionId": ""}, {"questionId": None}, {"questionId": "x"}]
        result = find_latest_unprocessed_question(qs, set())
        assert result == {"questionId": "x"}


class TestQuestionLabel:
    def test_normal(self):
        q = {
            "questionIndex": 3,
            "content": "<b>2+2=?</b>",
            "options": [{"mark": "A"}, {"mark": "B"}],
        }
        assert question_label(q) == "第3题 2+2=? [A/B]"

    def test_missing_index(self):
        q = {"content": "x", "options": [{"mark": "A"}]}
        assert question_label(q) == "第?题 x [A]"

    def test_no_options(self):
        q = {"questionIndex": 1, "content": "y"}
        assert question_label(q) == "第1题 y []"


class TestProgressText:
    def test_normal(self):
        data = {
            "data": {
                "answerRecord": {"answerRecordScore": 5},
                "answerSheet": {"score": 80, "answerProgress": 50},
            }
        }
        text = progress_text(data)
        assert "本题 5" in text
        assert "总分 80" in text
        assert "作答 50%" in text

    def test_empty(self):
        text = progress_text({})
        assert "?" in text

    def test_missing_record(self):
        text = progress_text({"data": {"answerSheet": {"score": 10}}})
        assert "总分 10" in text
        assert "本题 ?" in text


class TestParseIso:
    def test_normal(self):
        dt = parse_iso("2026-06-18T12:51:40.000Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.month == 6 and dt.day == 18

    def test_none(self):
        assert parse_iso(None) is None

    def test_empty(self):
        assert parse_iso("") is None

    def test_invalid(self):
        assert parse_iso("not a date") is None


class TestFormatTime:
    def test_normal(self):
        s = format_time("2026-06-18T12:51:40.000Z")
        assert "06-18" in s
        assert ":" in s

    def test_none(self):
        assert format_time(None) == "?"

    def test_invalid(self):
        assert format_time("bad") == "?"


class TestDeadlineCell:
    def test_no_deadline(self):
        cell = deadline_cell({})
        assert isinstance(cell, Text)
        assert "无截止" in cell.plain

    def test_already_past(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        cell = deadline_cell({"deadline": past})
        assert "已截止" in cell.plain
        assert "red" in str(cell.style)

    def test_within_one_hour(self):
        soon = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        cell = deadline_cell({"deadline": soon})
        assert "即将截止" in cell.plain
        assert "red" in str(cell.style)

    def test_within_one_day(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        cell = deadline_cell({"deadline": future})
        assert "h后" in cell.plain
        assert "yellow" in str(cell.style)

    def test_far_future(self):
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        cell = deadline_cell({"deadline": future})
        assert cell.plain.strip() != ""
        assert "green" in str(cell.style)


class TestEnsureLoggedIn:
    def test_skips_login_when_alive(self, monkeypatch):
        called = {"login": False, "alive": False}
        monkeypatch.setattr(main, "is_session_alive", lambda s: (called.__setitem__("alive", True) or True))
        monkeypatch.setattr(main, "login", lambda *a: called.__setitem__("login", True))
        ensure_logged_in = main.ensure_logged_in
        ensure_logged_in(MagicMock(), "u", "p")
        assert called["alive"] is True
        assert called["login"] is False

    def test_logs_in_when_dead(self, monkeypatch):
        called = {"login": 0}
        monkeypatch.setattr(main, "is_session_alive", lambda s: False)
        monkeypatch.setattr(main, "login", lambda *a: called.__setitem__("login", called["login"] + 1) or {"ok": True})
        ensure_logged_in = main.ensure_logged_in
        ensure_logged_in(MagicMock(), "u", "p")
        assert called["login"] == 1


class TestGetAllHomeworks:
    def test_single_page_when_under_page_size(self, monkeypatch):
        page_data = {"data": {"records": [{"id": "1"}, {"id": "2"}], "total": 2}}
        monkeypatch.setattr(main, "fetch_homework_page", lambda *a: page_data)
        result = main.get_all_homeworks(MagicMock(), "cid")
        assert [r["id"] for r in result] == ["1", "2"]

    def test_paginates_until_total_reached(self, monkeypatch):
        pages = [
            {"data": {"records": [{"id": str(i)} for i in range(20)], "total": 25}},
            {"data": {"records": [{"id": str(i)} for i in range(20, 25)], "total": 25}},
        ]
        calls = {"n": 0}

        def fake_fetch(s, cid, page_num, page_size):
            calls["n"] += 1
            return pages[page_num - 1]

        monkeypatch.setattr(main, "fetch_homework_page", fake_fetch)
        result = main.get_all_homeworks(MagicMock(), "cid")
        assert len(result) == 25
        assert calls["n"] == 2

    def test_stops_when_page_under_size_without_total(self, monkeypatch):
        page_data = {"data": {"records": [{"id": "1"}, {"id": "2"}]}}
        monkeypatch.setattr(main, "fetch_homework_page", lambda *a: page_data)
        result = main.get_all_homeworks(MagicMock(), "cid")
        assert len(result) == 2
