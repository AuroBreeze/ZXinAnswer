"""登录用例 — 编排认证流程，不关心 HTTP 细节。"""

import os

import config
from domain.exceptions import AuthenticationError
from domain.ports import AuthPort, CookiePort, PresenterPort


class LoginUseCase:
    """处理登录：cookie 复用 → 选择方式 → 执行登录。"""

    def __init__(self, auth: AuthPort, cookies: CookiePort, presenter: PresenterPort):
        self.auth = auth
        self.cookies = cookies
        self.presenter = presenter

    def ensure_logged_in(
        self, session, username: str | None = None, password: str | None = None
    ) -> None:
        if self.auth.is_session_alive(session):
            self.presenter.success("cookie 有效，跳过登录")
            return
        self.presenter.warning("cookie 失效，请选择登录方式")
        choice = self.presenter.select_item(
            [
                {"id": "1", "name": "微信扫码"},
                {"id": "2", "name": "账号密码"},
            ],
            [("方式", lambda item: item["name"])],
            "[bold cyan]请选择登录方式序号: [/bold cyan]",
        )
        if choice["id"] == "1":
            if not self.auth.login_wechat(session):
                raise AuthenticationError("扫码登录失败")
            self.presenter.success(f"登录成功，cookie 已保存到 {config.COOKIE_FILE}")
        else:
            if not username or not password:
                username = os.environ.get("ZXIN_USERNAME")
                password = os.environ.get("ZXIN_PASSWORD")
                if not username or not password:
                    raise AuthenticationError("请先设置环境变量 ZXIN_USERNAME 和 ZXIN_PASSWORD")
            self.auth.login_password(session, username, password)
            self.presenter.success(f"登录成功，cookie 已保存到 {config.COOKIE_FILE}")

    def logout(self, session) -> None:
        """清除当前 session 的 cookie 并删除本地 cookie 文件，重新走登录流程。"""
        self.cookies.clear(session)
        self.ensure_logged_in(session)