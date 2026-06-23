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

        env_username = os.environ.get("ZXIN_USERNAME")
        env_password = os.environ.get("ZXIN_PASSWORD")
        if env_username and env_password and username is None and password is None:
            self.presenter.info("检测到环境变量 ZXIN_USERNAME/ZXIN_PASSWORD，尝试登录...")
            try:
                self.auth.login_password(session, env_username, env_password)
                self.presenter.success(f"登录成功，cookie 已保存到 {config.COOKIE_FILE}")
                return
            except Exception as exc:
                self.presenter.warning(f"环境变量登录失败: {exc}")

        self.presenter.warning("cookie 失效，请选择登录方式")
        self._select_and_login(session)

    def _select_and_login(self, session) -> None:
        choice = self.presenter.select_item(
            [
                {"id": "1", "name": "微信扫码"},
                {"id": "2", "name": "手动输入账号密码"},
            ],
            [("方式", lambda item: item["name"])],
            "[bold cyan]请选择登录方式序号: [/bold cyan]",
        )
        if choice["id"] == "1":
            if not self.auth.login_wechat(session):
                raise AuthenticationError("扫码登录失败")
            self.presenter.success(f"登录成功，cookie 已保存到 {config.COOKIE_FILE}")
        else:
            self._login_password_interactive(session)

    def _login_password_interactive(self, session) -> None:
        while True:
            username = self.presenter.prompt("[bold cyan]请输入用户名: [/bold cyan]")
            password = self.presenter.prompt("[bold cyan]请输入密码: [/bold cyan]", password=True)
            if not username or not password:
                self.presenter.warning("用户名或密码不能为空")
                continue
            try:
                self.auth.login_password(session, username, password)
                self.presenter.success(f"登录成功，cookie 已保存到 {config.COOKIE_FILE}")
                return
            except Exception as exc:
                self.presenter.warning(f"登录失败: {exc}")
                retry = self.presenter.select_item(
                    [
                        {"id": "1", "name": "重新输入账号密码"},
                        {"id": "2", "name": "使用微信扫码"},
                    ],
                    [("方式", lambda item: item["name"])],
                    "[bold cyan]请选择: [/bold cyan]",
                )
                if retry["id"] == "2":
                    if not self.auth.login_wechat(session):
                        raise AuthenticationError("扫码登录失败")
                    self.presenter.success(f"登录成功，cookie 已保存到 {config.COOKIE_FILE}")
                    return

    def logout(self, session) -> None:
        """清除当前 session 的 cookie 并删除本地 cookie 文件，重新走登录流程。"""
        self.cookies.clear(session)
        self.ensure_logged_in(session)