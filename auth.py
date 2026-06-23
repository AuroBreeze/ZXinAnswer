"""登录 & session 管理：账号密码 / 微信扫码。"""

import os
import sys
import time
import uuid
from http.cookiejar import MozillaCookieJar
from typing import Any

import qrcode
import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

AUTH_HOST = "https://auth.z-xin.net"
LOGIN_URL = f"{AUTH_HOST}/api/portal/auth/login"
WECHAT_QRCODE_URL = f"{AUTH_HOST}/api/portal/wechat/qrcode"
WECHAT_LOGIN_CHECK_URL = f"{AUTH_HOST}/api/portal/wechat/login-check"
USER_SESSION_URL = "https://stu.z-xin.net/api/portal/user/session"
CLASSROOM_API_URL = "https://stu.z-xin.net/api/classroom"
CLASSROOM_PAYLOAD = {"action": "studentGet", "termId": "2015701567531511810"}

COOKIE_FILE = "cookies.txt"
QR_IMAGE_FILE = "zxin_qrcode.png"
SCAN_POLL_SECONDS = 3

SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://stu.z-xin.net",
    "Referer": "https://stu.z-xin.net/",
}


class ApiError(RuntimeError):
    pass


def assert_api_ok(response: requests.Response) -> dict[str, Any]:
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        raise ApiError(f"响应不是合法 JSON: {exc} | body={response.text[:200]}") from exc

    if not isinstance(data, dict):
        raise ApiError(f"响应顶层不是对象: {data!r}")

    code = data.get("code")
    success = data.get("success")
    if code is not None and code not in (0, 200, "0", "200") and success is not True:
        msg = data.get("msg") or data.get("message")
        raise ApiError(f"业务错误 code={code!r} msg={msg!r}")
    if success is False:
        msg = data.get("msg") or data.get("message")
        raise ApiError(f"业务失败 success=False msg={msg!r}")
    return data


def load_credentials() -> tuple[str, str]:
    username = os.environ.get("ZXIN_USERNAME")
    password = os.environ.get("ZXIN_PASSWORD")
    if not username or not password:
        raise RuntimeError("请先设置环境变量 ZXIN_USERNAME 和 ZXIN_PASSWORD")
    return username, password


def make_session(cookie_file: str = COOKIE_FILE) -> requests.Session:
    session = requests.Session()
    session.cookies = MozillaCookieJar(cookie_file)
    try:
        session.cookies.load(ignore_discard=True, ignore_expires=True)
        console.print(f"[green]✓[/green] 已加载 cookie: {cookie_file}")
    except FileNotFoundError:
        console.print("[yellow]→[/yellow] 未找到本地 cookie，将重新登录")

    session.headers.update(SESSION_HEADERS)
    return session


def login(session: requests.Session, username: str, password: str) -> dict[str, Any]:
    response = session.post(
        LOGIN_URL,
        json={"username": username, "password": password},
        timeout=20,
    )
    data = assert_api_ok(response)
    session.cookies.save(ignore_discard=True, ignore_expires=True)
    return data


def _print_qr_ascii(url: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    for y in range(0, len(matrix), 2):
        line = []
        for x in range(len(matrix[0])):
            top = matrix[y][x]
            bot = matrix[y + 1][x] if y + 1 < len(matrix) else False
            if top and bot:
                line.append("█")
            elif top:
                line.append("▀")
            elif bot:
                line.append("▄")
            else:
                line.append(" ")
        console.print("".join(line), end="")
        console.print()


def wechat_qrcode_login(session: requests.Session) -> bool:
    scene_id = str(uuid.uuid4())
    console.print(f"[cyan]→[/cyan] 生成登录会话: {scene_id[:8]}...")

    headers = {"Referer": f"{AUTH_HOST}/login"}
    resp = session.get(f"{WECHAT_QRCODE_URL}/{scene_id}", headers=headers, timeout=15)
    data = assert_api_ok(resp)
    qr_data = data["data"]
    qr_url = qr_data.get("url") or qr_data.get("ticket") or ""
    expire_seconds = qr_data.get("expire_seconds", 180)
    if not qr_url:
        raise ApiError(f"二维码响应缺少 url 字段: {data!r}")

    try:
        img = qrcode.make(qr_url)
        img.save(QR_IMAGE_FILE)
    except Exception as exc:
        console.print(f"[yellow]⚠ 保存 PNG 失败: {exc}[/yellow]")

    console.print(Panel.fit(
        "微信扫码登录\n请用微信扫描下方二维码（或打开图片/链接）",
        border_style="green",
    ))
    _print_qr_ascii(qr_url)
    console.print(f"[dim]PNG: {QR_IMAGE_FILE}[/dim]")
    console.print(f"[dim]URL: {qr_url}[/dim]")
    console.print(f"[dim]有效期: {expire_seconds}s[/dim]\n")

    console.print("[cyan]等待扫码...[/cyan]")
    start = time.time()
    scanned = False
    while True:
        if time.time() - start > expire_seconds:
            console.print("[red]✗ 二维码已过期，请重新登录[/red]")
            return False
        try:
            resp = session.get(
                WECHAT_LOGIN_CHECK_URL, params={"scene": scene_id}, headers=headers, timeout=15
            )
            data = resp.json()
            code = data.get("code")
            if code == 200:
                console.print("[green]✓ 登录成功[/green]")
                session.cookies.save(ignore_discard=True, ignore_expires=True)
                console.print(f"[green]✓ cookie 已保存到 {COOKIE_FILE}[/green]")
                return True
            if code == 202:
                if not scanned:
                    console.print("\n[yellow]已扫码，请在手机上确认...[/yellow]")
                    scanned = True
            else:
                console.print(".", end="")
                sys.stdout.flush()
        except requests.RequestException as exc:
            console.print(f"\n[yellow]⚠ 轮询异常: {exc}[/yellow]")
        time.sleep(SCAN_POLL_SECONDS)
    return False


def is_session_alive(session: requests.Session) -> bool:
    try:
        response = session.post(CLASSROOM_API_URL, json=CLASSROOM_PAYLOAD, timeout=20)
    except requests.RequestException:
        return False
    try:
        assert_api_ok(response)
    except (requests.RequestException, ApiError):
        return False
    return True