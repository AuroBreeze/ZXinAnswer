# Multi-Select Homework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-select homework input to automatic answer mode and answer selected homework serially.

**Architecture:** Keep menu interaction in `ConsolePresenter`, add a focused multi-select method beside the existing single-select method, and expose it through `HomeworkUseCase.select_homeworks()`. `main.py` will iterate the selected `Homework` entities and reuse the existing question fetch and answer flow for each one.

**Tech Stack:** Python 3.12, requests, rich, pytest, existing Clean Architecture-style layers.

---

## File Structure

- Modify `adapters/presenter.py`: add `_parse_selection_indexes()` and `ConsolePresenter.select_items()`.
- Modify `use_cases/homework.py`: add `HomeworkUseCase.select_homeworks()` while keeping `select_homework()` for compatibility.
- Modify `main.py`: replace automatic-answer single homework selection with multi-selection and serial execution.
- Modify `test_main.py`: add parser, presenter, use case, and main-flow tests.

### Task 1: Multi-Select Parser And Presenter Method

**Files:**
- Modify: `adapters/presenter.py`
- Test: `test_main.py`

- [ ] **Step 1: Add failing parser tests**

Append these tests near the existing presenter helper tests in `test_main.py`:

```python
from adapters.presenter import _parse_selection_indexes


class TestParseSelectionIndexes:
    def test_single_index(self):
        assert _parse_selection_indexes("2", 5) == [1]

    def test_comma_separated(self):
        assert _parse_selection_indexes("1,3,5", 5) == [0, 2, 4]

    def test_range(self):
        assert _parse_selection_indexes("2-4", 5) == [1, 2, 3]

    def test_mixed_input(self):
        assert _parse_selection_indexes("1,3-5,2", 5) == [0, 2, 3, 4, 1]

    def test_deduplicates_preserving_order(self):
        assert _parse_selection_indexes("2,2,1-3", 5) == [1, 0, 2]

    @pytest.mark.parametrize("value", ["", "0", "6", "a", "1,,2", "3-1", "1-a"])
    def test_invalid_input(self, value):
        with pytest.raises(ValueError):
            _parse_selection_indexes(value, 5)
```

- [ ] **Step 2: Run parser tests and verify failure**

Run: `uv run pytest test_main.py::TestParseSelectionIndexes -q`

Expected: FAIL because `_parse_selection_indexes` is not defined or imported.

- [ ] **Step 3: Implement parser and presenter method**

In `adapters/presenter.py`, add this helper after `_deadline_cell()`:

```python
def _parse_selection_indexes(value: str, item_count: int) -> list[int]:
    value = value.strip()
    if not value:
        raise ValueError("empty selection")

    indexes: list[int] = []
    seen: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            raise ValueError("empty selection token")
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                raise ValueError("invalid range")
            start = int(parts[0])
            end = int(parts[1])
            if start > end:
                raise ValueError("reversed range")
            numbers = range(start, end + 1)
        else:
            if not token.isdigit():
                raise ValueError("invalid index")
            numbers = [int(token)]

        for number in numbers:
            if number < 1 or number > item_count:
                raise ValueError("index out of range")
            index = number - 1
            if index not in seen:
                seen.add(index)
                indexes.append(index)

    if not indexes:
        raise ValueError("empty selection")
    return indexes
```

Add this method to `ConsolePresenter` after `select_item()`:

```python
    def select_items(
        self,
        items: list[dict],
        columns: list[tuple[str, Callable[[dict], object]]],
        prompt: str,
        allow_back: bool = False,
    ) -> list[dict] | None:
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
            try:
                indexes = _parse_selection_indexes(value, len(items))
            except ValueError:
                console.print("[red]请输入有效序号，示例: 1,3-5,8[/red]")
                continue
            return [items[index] for index in indexes]
```

- [ ] **Step 4: Run parser tests and verify pass**

Run: `uv run pytest test_main.py::TestParseSelectionIndexes -q`

Expected: PASS.

- [ ] **Step 5: Add failing presenter method tests**

Append these tests near `TestSelectItemExit` in `test_main.py`:

```python
class TestSelectItems:
    def test_selects_multiple_items(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["1,3"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        items = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        result = presenter.select_items(items, [("id", lambda x: x["id"])], "prompt", allow_back=True)
        assert result == [{"id": "1"}, {"id": "3"}]

    def test_back_returns_none(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["b"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        result = presenter.select_items([{"id": "1"}], [("id", lambda x: x["id"])], "prompt", allow_back=True)
        assert result is None

    def test_invalid_then_valid(self, monkeypatch):
        presenter = ConsolePresenter()
        inputs = iter(["9", "2"])
        monkeypatch.setattr("adapters.presenter.console.input", lambda *a, **k: next(inputs))
        items = [{"id": "1"}, {"id": "2"}]
        result = presenter.select_items(items, [("id", lambda x: x["id"])], "prompt")
        assert result == [{"id": "2"}]
```

- [ ] **Step 6: Run presenter tests**

Run: `uv run pytest test_main.py::TestSelectItems -q`

Expected: PASS after Step 3 implementation.

### Task 2: Homework Use Case Multi-Selection

**Files:**
- Modify: `use_cases/homework.py`
- Test: `test_main.py`

- [ ] **Step 1: Add failing use case tests**

Append these tests near other homework use case tests in `test_main.py`:

```python
class TestHomeworkUseCaseSelectHomeworks:
    def test_select_homeworks_returns_multiple_entities(self):
        api = MagicMock()
        api.get_homeworks.return_value = [
            Homework("h1", "HW1", 0, 0, None, None),
            Homework("h2", "HW2", 0, 0, None, None),
            Homework("h3", "HW3", 0, 0, None, None),
        ]
        presenter = MagicMock()
        presenter.select_items.return_value = [
            {"id": "h3", "name": "HW3", "score": 0, "progress": 0, "create_time": None, "deadline": None},
            {"id": "h1", "name": "HW1", "score": 0, "progress": 0, "create_time": None, "deadline": None},
        ]
        uc = HomeworkUseCase(api, presenter)

        result = uc.select_homeworks(MagicMock(), "c1")

        assert [homework.id for homework in result] == ["h3", "h1"]

    def test_select_homeworks_returns_none_on_back(self):
        api = MagicMock()
        api.get_homeworks.return_value = [Homework("h1", "HW1", 0, 0, None, None)]
        presenter = MagicMock()
        presenter.select_items.return_value = None
        uc = HomeworkUseCase(api, presenter)

        assert uc.select_homeworks(MagicMock(), "c1") is None
```

- [ ] **Step 2: Run use case tests and verify failure**

Run: `uv run pytest test_main.py::TestHomeworkUseCaseSelectHomeworks -q`

Expected: FAIL because `select_homeworks()` does not exist.

- [ ] **Step 3: Implement `select_homeworks()`**

In `use_cases/homework.py`, add this method after `select_homework()`:

```python
    def select_homeworks(self, session, classroom_id: str) -> list[Homework] | None:
        homeworks = self.api.get_homeworks(session, classroom_id)
        if not homeworks:
            self.presenter.warning("当前课程没有作业")
            return None
        self.presenter.info("作业列表")
        hw_dicts = [
            {
                "id": h.id,
                "name": h.name,
                "score": h.answer_sheet_score,
                "progress": h.answer_progress,
                "create_time": h.create_time,
                "deadline": h.deadline,
            }
            for h in homeworks
        ]
        selected = self.presenter.select_items(
            hw_dicts,
            [
                ("作业名", lambda h: h["name"]),
                ("得分", lambda h: str(h["score"])),
                ("作答", lambda h: f"{h['progress']}%"),
                ("创建时间", lambda h: _format_time(h["create_time"])),
                ("截止时间", _deadline_cell),
            ],
            "[bold cyan]请选择作业序号，支持 1,3-5,8: [/bold cyan]",
            allow_back=True,
        )
        if selected is None:
            return None
        selected_ids = [item["id"] for item in selected]
        by_id = {h.id: h for h in homeworks}
        return [by_id[homework_id] for homework_id in selected_ids]
```

- [ ] **Step 4: Run use case tests and verify pass**

Run: `uv run pytest test_main.py::TestHomeworkUseCaseSelectHomeworks -q`

Expected: PASS.

### Task 3: Main Flow Serial Execution

**Files:**
- Modify: `main.py`
- Test: `test_main.py`

- [ ] **Step 1: Add helper function for selected homework**

In `main.py`, add this function above `main()`:

```python
def answer_homeworks(session, homework_uc: HomeworkUseCase, answer_uc: AnswerUseCase, homeworks) -> None:
    for homework in homeworks:
        questions = homework_uc.get_questions(session, homework.id)
        answer_uc.answer_all(session, homework.id, questions)
```

- [ ] **Step 2: Add tests for serial helper**

Append this test to `test_main.py`:

```python
def test_answer_homeworks_runs_selected_homeworks_serially():
    from main import answer_homeworks

    session = MagicMock()
    homework_uc = MagicMock()
    answer_uc = MagicMock()
    homeworks = [
        Homework("h1", "HW1", 0, 0, None, None),
        Homework("h2", "HW2", 0, 0, None, None),
    ]
    homework_uc.get_questions.side_effect = [
        [Question("q1", 1, "", [])],
        [Question("q2", 1, "", [])],
    ]

    answer_homeworks(session, homework_uc, answer_uc, homeworks)

    assert homework_uc.get_questions.call_args_list[0].args == (session, "h1")
    assert homework_uc.get_questions.call_args_list[1].args == (session, "h2")
    assert answer_uc.answer_all.call_args_list[0].args[1] == "h1"
    assert answer_uc.answer_all.call_args_list[1].args[1] == "h2"
```

- [ ] **Step 3: Run helper test**

Run: `uv run pytest test_main.py::test_answer_homeworks_runs_selected_homeworks_serially -q`

Expected: PASS.

- [ ] **Step 4: Wire main automatic answer branch to multi-select**

Replace this block in `main.py`:

```python
                    homework = homework_uc.select_homework(session, course.id)
                    if homework is None:
                        continue
                    questions = homework_uc.get_questions(session, homework.id)
                    answer_uc.answer_all(session, homework.id, questions)
```

with:

```python
                    homeworks = homework_uc.select_homeworks(session, course.id)
                    if homeworks is None:
                        continue
                    answer_homeworks(session, homework_uc, answer_uc, homeworks)
```

Replace this repeated block inside the `again` loop:

```python
                        homework = homework_uc.select_homework(session, course.id)
                        if homework is None:
                            break
                        questions = homework_uc.get_questions(session, homework.id)
                        answer_uc.answer_all(session, homework.id, questions)
```

with:

```python
                        homeworks = homework_uc.select_homeworks(session, course.id)
                        if homeworks is None:
                            break
                        answer_homeworks(session, homework_uc, answer_uc, homeworks)
```

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest test_main.py::TestParseSelectionIndexes test_main.py::TestSelectItems test_main.py::TestHomeworkUseCaseSelectHomeworks test_main.py::test_answer_homeworks_runs_selected_homeworks_serially -q`

Expected: PASS.

### Task 4: Full Regression

**Files:**
- Verify: all project files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 2: Inspect git diff**

Run: `git diff -- main.py adapters/presenter.py use_cases/homework.py test_main.py docs/superpowers/specs/2026-06-24-multi-select-homework-design.md docs/superpowers/plans/2026-06-24-multi-select-homework.md`

Expected: diff only contains multi-select homework implementation, tests, and docs.

## Self-Review

- Spec coverage: The plan covers multi-format input, back/quit behavior, order-preserving deduplication, serial answer execution, unchanged single-select menus, and tests.
- Placeholder scan: No placeholders or deferred implementation steps remain.
- Type consistency: `select_items()` returns `list[dict] | None`; `select_homeworks()` returns `list[Homework] | None`; `answer_homeworks()` accepts selected homework entities and uses existing use cases.
