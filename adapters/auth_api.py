"""认证适配器 — 实现 AuthPort，封装 HTTP 调用。"""

import sys
import time
import uuid
from typing import Any

import requests

import config
from domain.exceptions import ApiError
from domain.ports import AuthPort

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, RuntimeError):
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


class AuthApiAdapter(AuthPort):
    def __init__(self, presenter, qr_generator):
        self.presenter = presenter
        self.qr = qr_generator

    def login_password(self, session: requests.Session, username: str, password: str) -> dict[str, Any]:
        response = session.post(
            config.LOGIN_URL,
            json={"username": username, "password": password},
            timeout=20,
        )
        data = assert_api_ok(response)
        session.cookies.save(ignore_discard=True, ignore_expires=True)
        return data

    def login_wechat(self, session: requests.Session) -> bool:
        import requests as req

        scene_id = str(uuid.uuid4())
        self.presenter.info(f"生成登录会话: {scene_id[:8]}...")

        headers = {"Referer": f"{config.AUTH_HOST}/login"}
        resp = session.get(f"{config.WECHAT_QRCODE_URL}/{scene_id}", headers=headers, timeout=15)
        data = assert_api_ok(resp)
        qr_data = data["data"]
        qr_url = qr_data.get("url") or qr_data.get("ticket") or ""
        expire_seconds = qr_data.get("expire_seconds", 180)
        if not qr_url:
            raise ApiError(f"二维码响应缺少 url 字段: {data!r}")

        try:
            self.qr.save_png(qr_url, config.QR_IMAGE_FILE)
        except Exception as exc:
            self.presenter.warning(f"保存 PNG 失败: {exc}")

        self.presenter.info("微信扫码登录")
        self.qr.generate_ascii(qr_url)
        self.presenter.info(f"PNG: {config.QR_IMAGE_FILE}")
        self.presenter.info(f"URL: {qr_url}")
        self.presenter.info(f"有效期: {expire_seconds}s")
        self.presenter.info("等待扫码...")

        start = time.time()
        scanned = False
        while True:
            if time.time() - start > expire_seconds:
                self.presenter.error("二维码已过期，请重新登录")
                return False
            try:
                resp = session.get(
                    config.WECHAT_LOGIN_CHECK_URL,
                    params={"scene": scene_id},
                    headers=headers,
                    timeout=15,
                )
                check_data = resp.json()
                code = check_data.get("code")
                if code == 200:
                    session.cookies.save(ignore_discard=True, ignore_expires=True)
                    return True
                if code == 202:
                    if not scanned:
                        self.presenter.warning("已扫码，请在手机上确认...")
                        scanned = True
                else:
                    print(".", end="", flush=True)
            except req.RequestException as exc:
                self.presenter.warning(f"轮询异常: {exc}")
            time.sleep(config.SCAN_POLL_SECONDS)

    def is_session_alive(self, session: requests.Session) -> bool:
        try:
            response = session.post(config.CLASSROOM_API_URL, json=config.CLASSROOM_PAYLOAD, timeout=20)
        except requests.RequestException:
            return False
        try:
            assert_api_ok(response)
        except (requests.RequestException, ApiError):
            return False
        return True