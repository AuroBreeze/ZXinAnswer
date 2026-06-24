"""作业查询用例 — 获取课程、作业列表、作业详情。"""

from domain.entities import Course, Homework, Question
from domain.ports import HomeworkPort, PresenterPort
from adapters.presenter import _format_time, _deadline_cell


class HomeworkUseCase:
    """编排课程/作业查询与选择。"""

    def __init__(self, homework_api: HomeworkPort, presenter: PresenterPort):
        self.api = homework_api
        self.presenter = presenter

    def select_course(self, session) -> Course:
        courses = self.api.get_courses(session)
        if not courses:
            raise RuntimeError("没有可选择的课程")
        self.presenter.info("课程列表")
        course_dicts = [
            {
                "id": c.id,
                "course_name": c.course_name,
                "teacher_name": c.teacher_name,
                "unfinished_count": c.unfinished_count,
            }
            for c in courses
        ]
        selected = self.presenter.select_item(
            course_dicts,
            [
                ("课程", lambda c: c["course_name"]),
                ("教师", lambda c: c["teacher_name"]),
                ("未完成", lambda c: str(c["unfinished_count"])),
            ],
            "[bold cyan]请选择课程序号: [/bold cyan]",
        )
        return next(c for c in courses if c.id == selected["id"])

    def select_homework(self, session, classroom_id: str) -> Homework | None:
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
        selected = self.presenter.select_item(
            hw_dicts,
            [
                ("作业名", lambda h: h["name"]),
                ("得分", lambda h: str(h["score"])),
                ("作答", lambda h: f"{h['progress']}%"),
                ("创建时间", lambda h: _format_time(h["create_time"])),
                ("截止时间", _deadline_cell),
            ],
            "[bold cyan]请选择作业序号: [/bold cyan]",
            allow_back=True,
        )
        if selected is None:
            return None
        return next(h for h in homeworks if h.id == selected["id"])

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

    def get_questions(self, session, homework_id: str) -> list[Question]:
        return self.api.get_homework_detail(session, homework_id)
