"""Cookie 存储适配器 — 实现 CookiePort，使用 MozillaCookieJar。"""

import os

import requests
from http.cookiejar import MozillaCookieJar

import config
from adapters.presenter import console


class CookieStoreAdapter:
    """实现 CookiePort，管理 cookie 文件加载与保存。"""

    def create_session(self, filepath: str = config.COOKIE_FILE) -> requests.Session:
        session = requests.Session()
        session.cookies = MozillaCookieJar(filepath)
        try:
            session.cookies.load(ignore_discard=True, ignore_expires=True)
            console.print(f"[green]✓[/green] 已加载 cookie: {filepath}")
        except FileNotFoundError:
            console.print("[yellow]→[/yellow] 未找到本地 cookie，将重新登录")

        session.headers.update(config.SESSION_HEADERS)
        return session

    def save(self, session: requests.Session, filepath: str = config.COOKIE_FILE) -> None:
        session.cookies.save(ignore_discard=True, ignore_expires=True)
        console.print(f"[green]✓[/green] cookie 已保存到 {filepath}")

    def clear(self, session: requests.Session, filepath: str = config.COOKIE_FILE) -> None:
        session.cookies.clear()
        session.cookies = MozillaCookieJar(filepath)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        console.print(f"[yellow]→[/yellow] 已退出账号，cookie 已清除: {filepath}")