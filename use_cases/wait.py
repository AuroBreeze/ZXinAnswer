"""等待新题用例 — 消息心跳 + 作业轮询，自动作答新出现的题目。"""

import time

import config
from domain.entities import Question
from domain.ports import HomeworkPort, MessagePort, PresenterPort

FALLBACK_INTERVAL = 60


class WaitLatestUseCase:
    """使用消息未读数为轻量心跳探测新题，避免高频轮询作业 API 被限流。"""

    def __init__(self, homework_api: HomeworkPort, presenter: PresenterPort,
                 message_api: MessagePort | None = None):
        self.api = homework_api
        self.presenter = presenter
        self.msg = message_api

    def execute(self, session, classroom_id: str, poll_seconds: int = config.POLL_SECONDS) -> None:
        processed_by_homework: dict[str, set[str]] = {}
        last_unread = self._get_unread(session)
        last_fallback = time.time()

        while True:
            try:
                unread = self._get_unread(session)
                now = time.time()

                if unread != last_unread or (now - last_fallback) >= FALLBACK_INTERVAL:
                    if unread != last_unread and self.msg:
                        self.presenter.info(f"检测到新消息（未读 {last_unread} → {unread}）")
                    homeworks = self.api.get_homeworks(session, classroom_id)
                    if not homeworks:
                        self.presenter.info("暂无作业，继续等待...")
                        last_unread = unread
                        last_fallback = now
                        time.sleep(poll_seconds)
                        continue
                    homework = homeworks[0]
                    homework_id = homework.id
                    processed = processed_by_homework.setdefault(homework_id, set())

                    questions = self.api.get_homework_detail(session, homework_id)
                    question = self._find_latest_unprocessed(questions, processed)
                    if question:
                        self.presenter.show_new_question(question)
                        mark, result = self._submit_until_correct(session, homework_id, question)
                        processed.add(question.question_id)
                        self.presenter.show_answer_result(mark)
                    else:
                        self.presenter.info("暂无新题，继续等待...")
                    last_unread = unread
                    last_fallback = now
                else:
                    self.presenter.info("暂无新题，继续等待...")
            except RuntimeError as exc:
                self.presenter.warning(f"等待中: {exc}")
            time.sleep(poll_seconds)

    def _get_unread(self, session) -> int:
        if self.msg:
            return self.msg.get_unread_count(session)
        return 0

    def _submit_until_correct(self, session, homework_id: str, question: Question):
        import requests as req
        last_result = None
        options = question.options
        for index, option in enumerate(options, start=1):
            try:
                result = self.api.submit_answer(session, homework_id, question.question_id, option.mark)
            except req.RequestException as exc:
                self.presenter.warning(f"网络异常，继续轮询: {exc}")
                break
            last_result = result
            self.presenter.show_answer_attempt(index, len(options), option.mark, result)
            if result.is_correct:
                return option.mark, result
        return None, last_result

    @staticmethod
    def _find_latest_unprocessed(questions: list[Question], processed: set[str]) -> Question | None:
        for question in reversed(questions):
            if question.question_id and question.question_id not in processed:
                return question
        return None