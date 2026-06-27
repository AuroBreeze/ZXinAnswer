"""组合根 — 实例化 adapters，注入 use cases，编排 CLI 流程。

依赖方向: main → use_cases → domain ← adapters
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, RuntimeError):
    pass

import requests

from adapters.auth_api import AuthApiAdapter
from adapters.cookie_store import CookieStoreAdapter
from adapters.homework_api import HomeworkApiAdapter
from adapters.message_api import MessageApiAdapter
from adapters.presenter import ConsolePresenter
from adapters.qr import QRGeneratorAdapter
from domain.exceptions import ApiError, AuthenticationError, ExitRequested
from use_cases.answer import AnswerUseCase
from use_cases.homework import HomeworkUseCase
from use_cases.login import LoginUseCase
from use_cases.wait import WaitLatestUseCase


def select_mode(presenter: ConsolePresenter) -> dict | None:
    return presenter.select_item(
        [
            {"id": "1", "name": "选择作业自动答完"},
            {"id": "2", "name": "等待最新题目"},
            {"id": "3", "name": "退出账号（重新登录）"},
        ],
        [("模式", lambda item: item["name"])],
        "[bold cyan]请选择模式序号: [/bold cyan]",
        allow_back=True,
    )


def answer_homeworks(session, homework_uc: HomeworkUseCase, answer_uc: AnswerUseCase, homeworks) -> None:
    for homework in homeworks:
        questions = homework_uc.get_questions(session, homework.id)
        answer_uc.answer_all(session, homework.id, questions)


def main() -> int:
    presenter = ConsolePresenter()
    cookies = CookieStoreAdapter()
    qr = QRGeneratorAdapter()
    auth_api = AuthApiAdapter(presenter, qr)
    homework_api = HomeworkApiAdapter()

    login_uc = LoginUseCase(auth_api, cookies, presenter)
    homework_uc = HomeworkUseCase(homework_api, presenter)
    answer_uc = AnswerUseCase(homework_api, presenter)
    message_api = MessageApiAdapter()
    wait_uc = WaitLatestUseCase(homework_api, presenter, message_api)

    presenter.show_banner()
    try:
        session = cookies.create_session()
        login_uc.ensure_logged_in(session)

        while True:
            course = homework_uc.select_course(session)

            while True:
                mode = select_mode(presenter)
                if mode is None:
                    break
                if mode["id"] == "1":
                    homeworks = homework_uc.select_homeworks(session, course.id)
                    if homeworks is None:
                        continue
                    answer_homeworks(session, homework_uc, answer_uc, homeworks)
                    while True:
                        again = presenter.prompt(
                            "[bold cyan]再答一份? (Enter 继续, b 返回模式选择, q 退出): [/bold cyan]"
                        ).lower()
                        if again == "q":
                            return 0
                        if again == "b":
                            break
                        homeworks = homework_uc.select_homeworks(session, course.id)
                        if homeworks is None:
                            break
                        answer_homeworks(session, homework_uc, answer_uc, homeworks)
                    if again == "q":
                        return 0
                    continue
                elif mode["id"] == "2":
                    wait_uc.execute(session, course.id)
                    return 0
                elif mode["id"] == "3":
                    login_uc.logout(session)
                    break
    except (KeyboardInterrupt, ExitRequested):
        presenter.info("已退出")
        return 0
    except requests.RequestException as exc:
        presenter.error(f"请求失败: {exc}")
        return 1
    except (RuntimeError, ApiError, AuthenticationError) as exc:
        presenter.error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
