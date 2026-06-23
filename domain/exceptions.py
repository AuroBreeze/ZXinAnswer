"""领域异常。"""


class ApiError(RuntimeError):
    """API 业务错误。"""


class AuthenticationError(RuntimeError):
    """认证/登录失败。"""


class HomeworkError(RuntimeError):
    """作业数据结构异常。"""


class ExitRequested(Exception):
    """用户请求退出（在菜单中输入 q）。"""