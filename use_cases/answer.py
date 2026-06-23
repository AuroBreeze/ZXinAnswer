"""答题用例 — 暴力遍历选项，找到正确答案。"""

from domain.entities import AnswerResult, AnswerSummary, Question
from domain.ports import HomeworkPort, PresenterPort


class AnswerUseCase:
    """编排答题流程：遍历选项 → 提交 → 检查 → 汇总。"""

    def __init__(self, homework_api: HomeworkPort, presenter: PresenterPort):
        self.api = homework_api
        self.presenter = presenter

    def _submit_until_correct(self, session, homework_id: str, question: Question) -> tuple[str | None, AnswerResult]:
        last_result = None
        options = question.options
        for index, option in enumerate(options, start=1):
            result = self.api.submit_answer(session, homework_id, question.question_id, option.mark)
            last_result = result
            self.presenter.show_answer_attempt(index, len(options), option.mark, result)
            if result.is_correct:
                return option.mark, result
        return None, last_result

    def answer_all(self, session, homework_id: str, questions: list[Question]) -> list[AnswerSummary]:
        results = []
        total = len(questions)
        for index, question in enumerate(questions, start=1):
            self.presenter.show_question(question, index, total)
            mark, result = self._submit_until_correct(session, homework_id, question)
            self.presenter.show_answer_result(mark)
            results.append(AnswerSummary(
                question_index=question.question_index,
                mark=mark,
                is_correct=mark is not None,
            ))
        self.presenter.show_summary(results)
        return results