"""领域异常。"""


class ApiError(RuntimeError):
    """API 业务错误。"""


class AuthenticationError(RuntimeError):
    """认证/登录失败。"""


class HomeworkError(RuntimeError):
    """作业数据结构异常。"""