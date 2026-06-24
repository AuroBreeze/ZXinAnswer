# Multi-Select Homework Design

## Goal

Allow users to select multiple homework items in automatic answer mode and complete the selected homework serially in the order requested by the user.

## User Interaction

In mode `1` (`选择作业自动答完`), the homework list remains a table. The selection prompt accepts single indexes, comma-separated indexes, ranges, and mixed input:

- `2` selects one homework.
- `1,3,5` selects multiple homework items.
- `1-5` selects a continuous range.
- `1,3-5,8` selects mixed indexes and ranges.
- `b` returns to mode selection.
- `q` exits the program.

Invalid input re-prompts the user. Invalid input includes empty input, out-of-range indexes, malformed tokens, and reversed ranges such as `5-3`.

Repeated indexes are deduplicated while preserving the user's first selected order.

## Data Flow

`main.py` continues to own the CLI flow. When the user chooses automatic answering, it asks `HomeworkUseCase` for a list of homework items instead of a single item.

For each selected homework, `main.py` serially runs the existing flow:

1. Fetch homework questions through `HomeworkUseCase.get_questions()`.
2. Run `AnswerUseCase.answer_all()` for that homework.
3. Show the existing per-homework answer summary.

After all selected homework items finish, the existing follow-up prompt remains: `Enter 继续, b 返回模式选择, q 退出`. Pressing Enter opens the multi-select homework list again.

## Components

`ConsolePresenter` gains a multi-select method that mirrors `select_item()` table rendering and exit/back behavior, but returns `list[dict] | None`.

`HomeworkUseCase` gains `select_homeworks()`, which converts selected homework dictionaries back to `Homework` entities and returns `list[Homework] | None`.

Existing single-select flows remain unchanged for courses, modes, login options, and retry menus.

## Error Handling

Selection parsing errors are handled in the presenter and shown as terminal validation messages. API and answer errors continue to use the existing exception handling in `main.py`.

If one selected homework has no questions, the current `HomeworkError` behavior remains unchanged and exits through the existing top-level error handling. The feature does not introduce partial-failure recovery.

## Testing

Tests should cover:

- Parsing single index input.
- Parsing comma-separated input.
- Parsing ranges.
- Parsing mixed input.
- Deduplicating repeated indexes while preserving order.
- Rejecting empty, malformed, out-of-range, and reversed-range input.
- Returning `None` on back input when allowed.
- `HomeworkUseCase.select_homeworks()` returning multiple `Homework` entities in selected order.
