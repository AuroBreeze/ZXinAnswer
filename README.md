# zxin 作业助手

知新芸（z-xin.net）教学平台作业自动答题脚本，基于 Clean Architecture。

## 功能

- **账号密码登录**：支持环境变量 `ZXIN_USERNAME` / `ZXIN_PASSWORD` 自动登录，也支持手动输入
- **微信扫码登录**：终端生成 ASCII 二维码 + 保存 PNG 图片，微信扫码即可登录
- **Cookie 复用**：登录一次后自动保存，下次启动无需重新登录
- **答题模式**：选择作业，自动遍历所有题目选项，找到正确答案
- **轮询模式**：持续监控最新作业，新题自动作答
- **截止时间高亮**：已截止（红）、1 小时内紧急（红）、24 小时内（黄）、正常（绿）
- **回退/退出/登出**：各级菜单支持 `b` 返回、`q` 退出、退出账号重新登录

## 项目结构

```
zxin/
├── domain/                 # 领域层（实体 + 异常 + 端口接口），零外部依赖
│   ├── entities.py           Course, Homework, Question, AnswerResult 等
│   ├── exceptions.py         ApiError, AuthenticationError, ExitRequested
│   └── ports.py              AuthPort, HomeworkPort, PresenterPort 等抽象
├── use_cases/              # 用例层（业务逻辑），只依赖 domain 端口
│   ├── login.py              LoginUseCase
│   ├── homework.py           HomeworkUseCase
│   ├── answer.py             AnswerUseCase
│   └── wait.py               WaitLatestUseCase
├── adapters/               # 适配器层（端口实现），依赖外部框架
│   ├── auth_api.py           AuthApiAdapter → requests HTTP
│   ├── homework_api.py       HomeworkApiAdapter → requests HTTP
│   ├── presenter.py          ConsolePresenter → rich
│   ├── qr.py                 QRGeneratorAdapter → qrcode
│   └── cookie_store.py       CookieStoreAdapter → MozillaCookieJar
├── config.py               # 全局常量 / URL
├── main.py                 # 组合根（入口）
├── test_main.py            # 测试（60 个用例）
└── pyproject.toml          # 项目配置（uv / Python 3.12+）
```

依赖方向：`main → use_cases → domain ← adapters`

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 运行

**微信扫码登录（无需环境变量）：**

```bash
uv run python main.py
# cookie 失效时会提示选择登录方式 → 选「微信扫码」
```

**账号密码登录（环境变量）：**

```powershell
# PowerShell
$env:ZXIN_USERNAME="你的手机号"
$env:ZXIN_PASSWORD="你的密码"
uv run python main.py
```

```bash
# Linux / macOS
ZXIN_USERNAME=13800138000 ZXIN_PASSWORD=yourpass uv run python main.py
```

### 3. 运行测试

```bash
uv run pytest
```

## 操作指南

```
启动 → 自动检测 cookie 是否有效
  ├─ 有效 → 直接进入课程列表
  └─ 失效 → 选择登录方式
       ├─ 1. 微信扫码 → 扫二维码 → 确认登录
       └─ 2. 手动输入账号密码

选择课程 → 选择模式
  ├─ 1. 选择作业自动答完 → 选作业 → 自动遍历提交 → 汇总
  │     └─ 答完后：(Enter 继续 / b 返回 / q 退出)
  ├─ 2. 等待最新题目 → 轮询监控新题自动作答
  └─ 3. 退出账号（重新登录）

所有菜单支持：b 返回上级 | q 退出程序 | Ctrl+C 退出
```

## 依赖

- Python >= 3.12
- [requests](https://pypi.org/project/requests/) — HTTP 请求
- [rich](https://pypi.org/project/rich/) — 终端美化输出
- [qrcode](https://pypi.org/project/qrcode/) — 二维码生成
- [Pillow](https://pypi.org/project/Pillow/) — 图片保存

## 免责声明

**本工具仅供学习交流用途，严禁用于以下场景：**

- 代他人完成作业或考试，获取不正当成绩
- 批量自动化操作，对平台服务器造成负担
- 破解、篡改、干扰教学平台的正常运行
- 任何违反学校规定或法律法规的行为

使用本工具即表示您已阅读并同意以上条款。开发者对因使用本工具产生的任何后果不承担责任，包括但不限于学业处分、账号封禁、法律责任等。

请尊重教育公平，诚实完成学业任务。
