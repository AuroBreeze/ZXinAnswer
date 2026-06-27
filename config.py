"""全局配置常量。"""

AUTH_HOST = "https://auth.z-xin.net"
STU_HOST = "https://stu.z-xin.net"

LOGIN_URL = f"{AUTH_HOST}/api/portal/auth/login"
WECHAT_QRCODE_URL = f"{AUTH_HOST}/api/portal/wechat/qrcode"
WECHAT_LOGIN_CHECK_URL = f"{AUTH_HOST}/api/portal/wechat/login-check"
USER_SESSION_URL = f"{STU_HOST}/api/portal/user/session"
CLASSROOM_API_URL = f"{STU_HOST}/api/classroom"
HOMEWORK_API_URL = f"{STU_HOST}/api/homework"
HOMEWORK_DETAIL_API_URL = f"{STU_HOST}/api/homework/detail"
ANSWER_RECORD_API_URL = f"{STU_HOST}/api/answer-record"
MESSAGE_API_URL = f"{STU_HOST}/api/message"

CLASSROOM_PAYLOAD = {"action": "studentGet", "termId": "2015701567531511810"}
HOMEWORK_PAGE_SIZE = 20
HOMEWORK_ORDER_BY = "createTime"
HOMEWORK_ORDER = "desc"

COOKIE_FILE = "cookies.txt"
QR_IMAGE_FILE = "zxin_qrcode.png"
POLL_SECONDS = 5
SCAN_POLL_SECONDS = 3

SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://stu.z-xin.net",
    "Referer": "https://stu.z-xin.net/",
}