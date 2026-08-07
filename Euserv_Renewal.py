# SPDX-License-Identifier: GPL-3.0-or-later
# Inspired by https://github.com/zensea/AutoEUServerlessWith2FA and https://github.com/WizisCool/AutoEUServerless

import os
import re
import time
import base64
from enum import Enum
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import imaplib
import email
from email.message import Message
from datetime import date
from typing import Any, Callable
import smtplib
from email.mime.text import MIMEText
import hmac
import struct
import ast
import operator
from html import escape as _html_escape


# 自定义异常类
class CaptchaError(Exception):
    """验证码处理相关错误"""


class PinRetrievalError(Exception):
    """PIN码获取相关错误"""


class LoginError(Exception):
    """登录相关错误"""


class RenewalError(Exception):
    """续期相关错误"""


# 环境变量配置
EUSERV_USERNAME = os.getenv("EUSERV_USERNAME", "")
EUSERV_PASSWORD = os.getenv("EUSERV_PASSWORD", "")
EUSERV_2FA = os.getenv("EUSERV_2FA", "")
CAPTCHA_USERID = os.getenv("CAPTCHA_USERID", "")
CAPTCHA_APIKEY = os.getenv("CAPTCHA_APIKEY", "")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
CLOUD_MAIL_API_URL = os.getenv("CLOUD_MAIL_API_URL", "")

# Telegram Bot 推送配置 (可选)
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_USER_ID = os.getenv("TG_USER_ID", "")
TG_API_HOST = (os.getenv("TG_API_HOST") or "").strip() or "https://api.telegram.org"

# 多账号配置 (可选)：账号级变量（EUSERV_USERNAME/PASSWORD/2FA 等）同一环境变量内用
# 英文逗号分隔多个值，按位置一一对应。邮箱服务级变量（CLOUD_MAIL_API_URL/EMAIL_HOST）
# 默认只填一个值，所有账号共用，无需按账号重复。
# 例如 EUSERV_USERNAME="user1@x.com,user2@y.com"，EUSERV_PASSWORD="pw1,pw2"。


def _split_multi(value: str) -> list[str]:
    """把逗号分隔的变量值拆成列表，去除首尾空白。"""
    if not value:
        return []
    return [item.strip() for item in value.split(",")]


def _at(values: list[str], index: int) -> str:
    """取值：变量只有一个值（未用逗号分隔）时广播给所有账号；多个值时按位置对应，越界返回空。"""
    if len(values) == 1:
        return values[0]
    return values[index] if index < len(values) else ""


def parse_accounts() -> list[dict]:
    """基于逗号分隔的环境变量构建账号列表。

    规则：EUSERV_USERNAME 含逗号即视为多账号模式。
    变量分为两类：
      - 账号级（EUSERV_PASSWORD、EUSERV_2FA、EMAIL_USERNAME、EMAIL_PASSWORD）：
        多账号时可逗号分隔、按位置一一对应；只填一个值则所有账号共用。
      - 邮箱服务级（CLOUD_MAIL_API_URL、EMAIL_HOST）：是整个邮箱服务的配置，
        正常情况下只填一个值，所有账号共用同一个 Cloud Mail 实例或同一套
        IMAP 服务；只有当账号确实各自部署了不同的邮箱服务时才按位置填多个。

    单账号（不含逗号）时返回空列表，走向后兼容的模块级常量路径。

    每个账号字典包含独立的 Euserv 凭据，以及邮箱凭据：
    name / username / password / two_fa / email_host / email_username /
    email_password / cloud_mail_api_url
    其中 cloud_mail_api_url、email_host 属于邮箱服务级配置：每个账号字段默认
    来自同一个共享值（单值广播），只在账号各自使用不同邮箱服务时才按位置不同。
    """
    usernames = _split_multi(EUSERV_USERNAME)
    if not usernames:
        return []
    if "," not in EUSERV_USERNAME:
        return []  # 单账号模式，保持向后兼容

    passwords = _split_multi(EUSERV_PASSWORD)
    two_fas = _split_multi(EUSERV_2FA)
    email_hosts = _split_multi(EMAIL_HOST)
    email_usernames = _split_multi(EMAIL_USERNAME)
    email_passwords = _split_multi(EMAIL_PASSWORD)
    cloud_mail_urls = _split_multi(CLOUD_MAIL_API_URL)

    accounts = []
    for i, username in enumerate(usernames):
        accounts.append(
            {
                "name": username,
                "username": username,
                "password": _at(passwords, i),
                "two_fa": _at(two_fas, i),
                "email_host": _at(email_hosts, i),
                "email_username": _at(email_usernames, i),
                "email_password": _at(email_passwords, i),
                "cloud_mail_api_url": _at(cloud_mail_urls, i),
            }
        )
    return accounts

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# 时间配置 (秒)
LOGIN_MAX_RETRY_COUNT = 5
PIN_WAIT_SECONDS = 30
HTTP_TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 5
SERVER_LIST_RETRY_DELAY = 30
API_TIMEOUT_SECONDS = 20
POST_RENEWAL_CHECK_DELAY = 15
EMAIL_CHECK_INTERVAL = 30
EMAIL_MAX_RETRIES = 3

# 退出码定义 (用于智能调度)
EXIT_SUCCESS = 0  # 续约成功或无需续约
EXIT_FAILURE = 1  # 续约失败，需要重试
EXIT_SKIPPED = 2  # 未到续约日期，跳过执行

# SMTP 配置 (可选环境变量)
# 163 等邮箱推送时使用 SMTP_USERNAME / SMTP_PASSWORD（独立于读取邮件的 EMAIL_* 凭据）
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "") or EMAIL_USERNAME
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "") or EMAIL_PASSWORD
SMTP_HOST = os.getenv("SMTP_HOST") or (
    EMAIL_HOST.replace("imap", "smtp") if EMAIL_HOST else ""
)
_smtp_port_env = os.getenv("SMTP_PORT", "")
SMTP_PORT = int(_smtp_port_env) if _smtp_port_env and _smtp_port_env.strip() else 465

# GitHub Actions 输出文件
GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT", "")

# 登录检测字符串常量
CAPTCHA_PROMPT = "To finish the login process please solve the following captcha."
TWO_FA_PROMPT = (
    "To finish the login process enter the PIN that is shown in yout authenticator app."
)
LOGIN_SUCCESS_INDICATORS = ("Hello", "Confirm or change your customer data here")
RENEWAL_DATE_PATTERN = r"Contract extension possible from"

# URL 常量
EUSERV_ORIGIN = "https://support.euserv.com"
EUSERV_BASE_URL = f"{EUSERV_ORIGIN}/index.iphp"
EUSERV_CAPTCHA_URL = f"{EUSERV_ORIGIN}/securimage_show.php"
TRUECAPTCHA_API_URL = "https://api.apitruecaptcha.org/one/gettext"


class LogLevel(Enum):
    """日志级别枚举"""

    INFO = "ℹ️"
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    PROGRESS = "🔄"
    CELEBRATION = "🎉"


def _hotp(key: str, counter: int, digits: int = 6, digest: str = "sha1") -> str:
    """HOTP 算法实现"""
    key_bytes = base64.b32decode(key.upper() + "=" * ((8 - len(key)) % 8))
    counter_bytes = struct.pack(">Q", counter)
    mac = hmac.new(key_bytes, counter_bytes, digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">L", mac[offset : offset + 4])[0] & 0x7FFFFFFF  # type: ignore[index]
    return str(binary)[-digits:].zfill(digits)  # type: ignore[index]


def _totp(key: str, time_step: int = 30, digits: int = 6, digest: str = "sha1") -> str:
    """TOTP 算法实现"""
    return _hotp(key, int(time.time() / time_step), digits, digest)


def _safe_eval_math(expr: str) -> int | None:
    """安全计算简单数学表达式 (仅支持 +, -, *, /)"""
    ops: dict[Any, Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.floordiv,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported expression")

    try:
        return int(_eval(ast.parse(expr, mode="eval").body))
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
        return None


def _clean_math_expr(raw: str) -> str:
    """统一清洗验证码数学表达式：替换常见字符并保留数字与运算符。"""
    cleaned = (
        raw.replace("x", "*")
        .replace("X", "*")
        .replace("=", "")
        .replace(" ", "")
        .strip()
    )
    return "".join(c for c in cleaned if c in "0123456789+-*/")


def _try_solve_math(raw: str) -> str | None:
    """尝试将原始文本作为数学表达式求解，失败返回 None。"""
    cleaned = _clean_math_expr(raw)
    if cleaned and any(op in cleaned for op in ["+", "-", "*", "/"]):
        result = _safe_eval_math(cleaned)
        if result is not None:
            return str(result)
    return None


class RenewalBot:
    """
    Euserv VPS 自动续期机器人类。

    封装了所有业务逻辑和状态，提供更好的可测试性和可维护性。
    """

    def __init__(self, account: dict | None = None):
        """初始化机器人实例。

        Args:
            account: 多账号模式下单个账号的凭据字典（由 parse_accounts 产生）；
                为 None 时使用模块级单账号环境变量。
        """
        self.account = account
        self.log_messages: list[str] = []
        self.current_login_attempt = 1
        self.session: requests.Session | None = None
        self.sess_id: str | None = None
        self._ocr = None  # OCR 实例懒加载
        self.next_renewal_date: str | None = None  # 本次运行算出的最早续约日期
        self._write_output = True

    # ---- 账号凭据（多账号时取自 account，单账号时回退全局环境变量）----

    def _creds(self, key: str, global_key: str) -> str | None:
        """返回账号级凭据，未配置时回退全局。"""
        if self.account is not None:
            return self.account.get(key)
        return globals().get(global_key, "")

    @property
    def username(self) -> str:
        return self._creds("username", "EUSERV_USERNAME") or ""

    @property
    def password(self) -> str:
        return self._creds("password", "EUSERV_PASSWORD") or ""

    @property
    def two_fa(self) -> str:
        return self._creds("two_fa", "EUSERV_2FA") or ""

    @property
    def email_host(self) -> str:
        return self._creds("email_host", "EMAIL_HOST") or ""

    @property
    def email_username(self) -> str:
        return self._creds("email_username", "EMAIL_USERNAME") or ""

    @property
    def email_password(self) -> str:
        return self._creds("email_password", "EMAIL_PASSWORD") or ""

    @property
    def cloud_mail_api_url(self) -> str:
        return self._creds("cloud_mail_api_url", "CLOUD_MAIL_API_URL") or ""

    @property
    def account_name(self) -> str:
        if self.account is not None:
            return str(self.account.get("name") or self.username)
        return self.username

    def _cleanup(self) -> None:
        """清理资源，关闭 HTTP Session"""
        if self.session:
            self.session.close()
            self.session = None

    # ==================== 日志相关 ====================

    def log(self, info: str, level: LogLevel = LogLevel.INFO) -> None:
        """记录日志消息到实例日志列表。"""
        formatted = f"{level.value} {info}" if level != LogLevel.INFO else info
        print(formatted)
        self.log_messages.append(formatted)

    # ==================== 配置验证 ====================

    def validate_config(self) -> tuple[bool, list[str]]:
        """验证必需配置，返回 (是否通过, 缺失项列表)。"""
        required = {
            "EUSERV_USERNAME": self.username,
            "EUSERV_PASSWORD": self.password,
            "EMAIL_USERNAME": self.email_username,
            "EMAIL_PASSWORD": self.email_password,
        }
        if not self.cloud_mail_api_url:
            required["EMAIL_HOST"] = self.email_host
        missing = [k for k, v in required.items() if not v]
        return len(missing) == 0, missing

    # ==================== 邮件发送 ====================

    def send_status_email(self, subject_status: str) -> None:
        """发送状态通知邮件。"""
        if not (NOTIFICATION_EMAIL and SMTP_USERNAME and SMTP_PASSWORD):
            self.log("邮件通知所需的一个或多个Secrets未设置，跳过发送邮件。")
            return
        if not SMTP_HOST:
            self.log("无法推断 SMTP 服务器地址，跳过发送邮件。")
            return
        self.log("正在准备发送状态通知邮件...")
        sender = SMTP_USERNAME
        recipient = NOTIFICATION_EMAIL
        subject = f"EUServ 续期脚本运行报告 — {subject_status}"
        body = "本次运行详细日志如下：\n\n" + "\n".join(self.log_messages)
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                if SMTP_PORT == 465:
                    server = smtplib.SMTP_SSL(
                        SMTP_HOST, SMTP_PORT, timeout=HTTP_TIMEOUT_SECONDS
                    )
                else:
                    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=HTTP_TIMEOUT_SECONDS)
                    server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_USERNAME, [recipient], msg.as_string())
                server.quit()
                self.log("状态通知邮件已成功发送！", LogLevel.CELEBRATION)
                return
            except smtplib.SMTPException as e:
                last_error = e
                self.log(
                    f"发送邮件失败 (尝试 {attempt}/3): {e} "
                    f"(host={SMTP_HOST}, port={SMTP_PORT})",
                    LogLevel.ERROR,
                )
                if attempt < 3:
                    time.sleep(10)
        self.log(f"邮件通知失败，多次尝试后仍未成功: {last_error}", LogLevel.ERROR)

    # ==================== Telegram 推送 ====================

    def send_telegram_notification(self, subject_status: str) -> None:
        """发送状态通知到 Telegram Bot。

        需要配置 TG_BOT_TOKEN 与 TG_USER_ID；未配置时跳过。
        """
        if not (TG_BOT_TOKEN and TG_USER_ID):
            self.log("Telegram 通知所需的一个或多个Secrets未设置，跳过发送。")
            return
        self.log("正在准备发送 Telegram 通知...")

        logs = "\n".join(self.log_messages)
        # Telegram 单条消息长度限制约 4096 字符，超出时截断。
        logs = logs[:3900]
        message = (
            f"<b>📋 EUServ 续期脚本运行报告 — {subject_status}</b>\n\n"
            f"本次运行详细日志如下：\n"
            f"<pre>{_html_escape(logs)}</pre>\n"
            f"🔗 <a href='https://github.com/wimdaw/EUServ_Renewal'>EUServ_Renewal</a>"
        )
        if len(self.log_messages) > 100:
            message += "\n\n<i>(日志过长已截断)</i>"

        data = {
            "chat_id": TG_USER_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
        try:
            resp = requests.post(
                f"{TG_API_HOST}/bot{TG_BOT_TOKEN}/sendMessage",
                data=data,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            body = resp.json().get("result", {})
            chat = body.get("chat", {})
            self.log(
                "Telegram 通知已成功发送！"
                f" (chat_id={chat.get('id')}, username=@{chat.get('username') or '-'}, "
                f"name={chat.get('first_name') or chat.get('title') or '-'})",
                LogLevel.CELEBRATION,
            )
        except requests.RequestException as e:
            detail = getattr(e.response, "text", "")[:300] if getattr(e, "response", None) else ""
            self.log(
                f"Telegram 推送失败: {e}"
                + (f" | 响应: {detail}" if detail else ""),
                LogLevel.ERROR,
            )

    # ==================== OCR 相关 ====================

    def _get_ocr(self):
        """获取或创建 OCR 实例（懒加载单例）"""
        if self._ocr is None:
            import ddddocr

            self._ocr = ddddocr.DdddOcr(show_ad=False)
        return self._ocr

    def prewarm_ocr(self) -> None:
        """预加载 OCR 模型，减少首次识别延迟"""
        self.log("正在预加载 OCR 模型...", LogLevel.PROGRESS)
        try:
            self._get_ocr()
            self.log("OCR 模型预加载完成", LogLevel.SUCCESS)
        except Exception as e:
            self.log(f"OCR 预加载失败 (将在需要时重试): {e}", LogLevel.WARNING)

    def _solve_captcha_local(self, image_bytes: bytes) -> str | None:
        """使用本地 ddddocr 识别验证码"""
        ocr = self._get_ocr()
        # Euserv 验证码可能是数学算式（如 3+x=）也可能是混合字母数字文本，
        # 放宽字符集，避免把字母验证码读成乱码。
        ocr.set_ranges("0123456789+-x/=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
        captcha_text = ocr.classification(image_bytes)

        if not captcha_text:
            return None

        # 尝试作为数学表达式计算
        result = _try_solve_math(captcha_text)
        return result if result else captcha_text

    def _solve_captcha_api(self, image_bytes: bytes) -> str | None:
        """使用 TrueCaptcha API 识别验证码"""
        encoded_string = base64.b64encode(image_bytes).decode("ascii")

        data = {
            "userid": CAPTCHA_USERID,
            "apikey": CAPTCHA_APIKEY,
            "data": encoded_string,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 使用全局 requests.post 而非 self.session.post，
                # 避免将 EUserv 的 cookies 发送到第三方 API
                api_response = requests.post(
                    url=TRUECAPTCHA_API_URL, json=data, timeout=API_TIMEOUT_SECONDS
                )
                api_response.raise_for_status()
                result_data = api_response.json()

                if result_data.get("status") == "error":
                    self.log(f"API返回错误: {result_data.get('message')}")
                    return None

                captcha_text = result_data.get("result")
                if captcha_text:
                    # 使用统一的数学表达式求解
                    result = _try_solve_math(captcha_text)
                    return result if result else captcha_text

            except requests.RequestException as e:
                self.log(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY_SECONDS)

        return None

    def _solve_captcha(self, image_bytes: bytes) -> str:
        """三保险验证码识别：本地 OCR 与 TrueCaptcha API 并行竞速，任一成功即用。

        若配置了 API，本地识别与 API 同时进行，谁先出结果用谁的；
        未配置 API 时仅使用本地 OCR。
        """
        api_configured = bool(CAPTCHA_USERID and CAPTCHA_APIKEY)
        self.log(
            f"正在识别验证码 (本地 OCR ddddocr + {'TrueCaptcha API' if api_configured else '无API，仅本地'})..."
        )

        if not api_configured:
            result = self._solve_captcha_local(image_bytes)
            if not result:
                raise CaptchaError("本地 OCR 识别失败且未配置 API 凭据")
            self.log(f"本地 OCR 识别成功: {result}")
            return result

        # API 优先：TrueCaptcha 对混合字母数字验证码准确率更高（本地 ddddocr
        # 毫秒级返回抢跑，但易把字母读错）。仅当 API 识别失败时才回退本地。
        try:
            api_result = self._solve_captcha_api(image_bytes)
        except CaptchaError:
            api_result = None
        if api_result:
            self.log(f"TrueCaptcha API 识别成功: {api_result}")
            return api_result

        self.log("TrueCaptcha API 识别失败，回退本地 OCR...")
        result = self._solve_captcha_local(image_bytes)
        if result:
            self.log(f"本地 OCR 识别成功: {result}")
            return result
        raise CaptchaError("本地 OCR 与 TrueCaptcha API 均无法识别验证码")

    # ==================== 验证码和2FA处理 ====================

    def _handle_captcha(self, url: str, captcha_image_url: str, headers: dict) -> requests.Response | None:
        """处理图片验证码，返回更新后的响应"""
        self.log("检测到图片验证码，正在处理...")
        image_res = self.session.get(
            captcha_image_url,
            headers={"user-agent": USER_AGENT},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        image_res.raise_for_status()
        image_bytes = image_res.content

        captcha_code = self._solve_captcha(image_bytes)

        self.log(f"验证码计算结果是: {captcha_code}")
        post_data = {
            "email": self.username,
            "password": self.password,
            "subaction": "login",
            "sess_id": self.sess_id,
            "captcha_code": str(captcha_code),
        }
        response = self.session.post(
            url, headers=headers, data=post_data, timeout=HTTP_TIMEOUT_SECONDS
        )

        if CAPTCHA_PROMPT in response.text:
            self.log("图片验证码验证失败")
            # 验证失败时保存验证码图片用于调试
            try:
                with open("captcha_failed.png", "wb") as f:
                    f.write(image_bytes)
                self.log(
                    f"失败的验证码图片已保存到 captcha_failed.png，识别结果为: {captcha_code}"
                )
            except OSError as e:
                self.log(f"保存验证码图片失败: {e}")
            return None
        self.log("图片验证码验证通过")
        return response

    def _handle_2fa(self, response_text: str) -> requests.Response | None:
        """处理2FA验证，返回更新后的响应"""
        self.log("检测到需要2FA验证")
        if not self.two_fa:
            self.log("未配置EUSERV_2FA Secret，无法进行2FA登录。")
            return None

        two_fa_code = _totp(self.two_fa)
        self.log(f"已生成2FA动态密码: ****{two_fa_code[-2:]}")  # type: ignore[index]

        soup = BeautifulSoup(response_text, "html.parser")
        hidden_inputs = soup.find_all("input", type="hidden")
        two_fa_data = {inp["name"]: inp.get("value", "") for inp in hidden_inputs}
        two_fa_data["pin"] = two_fa_code

        response = self.session.post(
            EUSERV_BASE_URL,
            headers={"user-agent": USER_AGENT, "origin": EUSERV_ORIGIN},
            data=two_fa_data,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        if TWO_FA_PROMPT in response.text:
            self.log("2FA验证失败")
            return None
        self.log("2FA验证通过")
        return response

    @staticmethod
    def _is_login_success(response_text: str) -> bool:
        """检查是否登录成功"""
        return any(indicator in response_text for indicator in LOGIN_SUCCESS_INDICATORS)

    # ==================== 登录流程 ====================

    def _refresh_session(self) -> None:
        """续期流程后重新登录，确保 session 未过期。"""
        self.log("续期操作时间较长，正在重新登录以刷新 session...")
        self._cleanup()
        self._perform_login()

    def _safe_refresh_session(self) -> None:
        """安全刷新 session，失败时仅记录警告而不影响主流程状态。"""
        try:
            self._refresh_session()
        except LoginError as e:
            self.log(f"刷新 session 失败 (不影响已提交的续约): {e}", LogLevel.WARNING)

    def _perform_login(self) -> None:
        """执行登录流程，包含重试逻辑。成功后设置 self.sess_id 和 self.session。"""
        headers = {"user-agent": USER_AGENT, "origin": EUSERV_ORIGIN}
        self.session = requests.Session()

        # 配置自动重试策略 (仅对连接错误和 5xx 状态码重试)
        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

        for attempt in range(LOGIN_MAX_RETRY_COUNT):
            self.current_login_attempt = attempt + 1
            if attempt > 0:
                self.log(f"登录尝试第 {attempt + 1}/{LOGIN_MAX_RETRY_COUNT} 次...")
                time.sleep(RETRY_DELAY_SECONDS)

            try:
                if self._attempt_login(headers):
                    return
            except (requests.RequestException, ValueError) as e:
                self.log(f"登录尝试失败: {e}")

        raise LoginError("登录失败次数过多，退出脚本。")

    def _attempt_login(self, headers: dict) -> bool:
        """单次登录尝试，成功返回 True 并设置 self.sess_id/self.session。"""
        sess_res = self.session.get(
            EUSERV_BASE_URL, headers=headers, timeout=HTTP_TIMEOUT_SECONDS
        )
        sess_res.raise_for_status()
        sess_id = sess_res.cookies.get("PHPSESSID")
        if not sess_id:
            raise ValueError("无法从初始响应的Cookie中找到PHPSESSID")

        # [C1 fix] 立即同步 sess_id，确保后续验证码/2FA 流程可用
        self.sess_id = sess_id

        # 模拟浏览器行为：请求 logo 以获取完整的 Cookie 链
        self.session.get(
            f"{EUSERV_ORIGIN}/pic/logo_small.png",
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
        )

        login_data = {
            "email": self.username,
            "password": self.password,
            "form_selected_language": "en",
            "Submit": "Login",
            "subaction": "login",
            "sess_id": sess_id,
        }
        response = self.session.post(
            EUSERV_BASE_URL,
            headers=headers,
            data=login_data,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        if self._is_login_success(response.text):
            self.log("登录成功")
            return True

        # 处理验证码
        if CAPTCHA_PROMPT in response.text:
            response = self._handle_captcha(EUSERV_BASE_URL, EUSERV_CAPTCHA_URL, headers)
            if response is None:
                return False

        # 处理2FA
        if TWO_FA_PROMPT in response.text:
            response = self._handle_2fa(response.text)
            if response is None:
                return False

        if self._is_login_success(response.text):
            self.log("登录成功")
            return True

        self.log("登录失败，所有验证尝试后仍未成功。")
        return False

    # ==================== PIN 码获取 ====================

    @staticmethod
    def _extract_email_body(msg: Message) -> str:
        """从邮件消息中提取正文内容"""
        def _decode_payload(part: Message) -> str:
            charset = part.get_content_charset() or "utf-8"
            payload = part.get_payload(decode=True)
            if payload is None:
                return ""
            if isinstance(payload, bytes):
                return payload.decode(charset, errors="replace")
            return str(payload)

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return _decode_payload(part)
            return ""
        return _decode_payload(msg)

    @staticmethod
    def _extract_pin_from_text(body: str) -> str | None:
        """从邮件正文中提取 6 位 PIN 码。"""
        pin_match = re.search(r"PIN:\s*\n?(\d{6})", body, re.IGNORECASE)
        if pin_match:
            return pin_match.group(1)
        return None

    def _fetch_pin_from_email(
        self, mail: imaplib.IMAP4_SSL, search_criteria: str
    ) -> str | None:
        """从邮箱中搜索并提取PIN码"""
        status, messages = mail.search(None, search_criteria)
        if status != "OK" or not messages[0]:
            return None

        latest_email_id = messages[0].split()[-1]
        _, data = mail.fetch(latest_email_id, "(RFC822)")
        if not data or not data[0] or not isinstance(data[0], tuple):
            return None
        raw_data = data[0][1]  # type: ignore
        if not isinstance(raw_data, bytes):
            return None
        raw_email = raw_data.decode("utf-8")
        msg = email.message_from_string(raw_email)
        body = self._extract_email_body(msg)

        return self._extract_pin_from_text(body)

    def _try_fetch_pin_once(self, search_criteria: str) -> str | None:
        """单次尝试从 Gmail 获取 PIN 码"""
        mail = imaplib.IMAP4_SSL(self.email_host or "imap.gmail.com")
        try:
            mail.login(self.email_username or "", self.email_password or "")
            mail.select("inbox")
            pin = self._fetch_pin_from_email(mail, search_criteria)
            if pin:
                self.log(f"成功从Gmail获取PIN码: ****{str(pin)[-2:]}")  # type: ignore[index]
                return pin
        finally:
            try:
                mail.logout()
            except Exception:
                pass
        return None

    def _get_pin_from_gmail(self) -> str:
        """从Gmail获取PIN码"""
        self.log("正在连接Gmail获取PIN码...")
        today_str = date.today().strftime("%d-%b-%Y")
        search_criteria = f'(SINCE "{today_str}" FROM "no-reply@euserv.com" SUBJECT "EUserv - PIN for the Confirmation of a Security Check")'

        last_error: Exception | None = None
        for i in range(EMAIL_MAX_RETRIES):
            try:
                pin = self._try_fetch_pin_once(search_criteria)
                if pin:
                    return pin
                self.log(f"第{i + 1}次尝试：未找到PIN邮件，等待{EMAIL_CHECK_INTERVAL}秒...")
                time.sleep(EMAIL_CHECK_INTERVAL)
            except (imaplib.IMAP4.error, OSError) as e:
                last_error = e
                self.log(f"获取PIN码时发生错误 (尝试 {i + 1}/{EMAIL_MAX_RETRIES}): {e}")
                if i < EMAIL_MAX_RETRIES - 1:
                    self.log(f"将在 {EMAIL_CHECK_INTERVAL} 秒后重试...")
                    time.sleep(EMAIL_CHECK_INTERVAL)
        if last_error:
            if isinstance(last_error, Exception):
                raise PinRetrievalError(f"邮件连接错误: {last_error}") from last_error
            raise PinRetrievalError(f"邮件连接错误: {last_error}")
        raise PinRetrievalError("多次尝试后仍无法获取PIN码邮件。")

    # ==================== Cloud Mail API PIN 获取 ====================

    def _cloud_mail_get_token(self, base_url: str) -> str:
        """通过 genToken 接口获取身份令牌。"""
        resp = requests.post(
            f"{base_url}/api/public/genToken",
            json={"email": self.email_username, "password": self.email_password},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        result = resp.json()
        if not isinstance(result, dict) or result.get("code") != 200:
            raise PinRetrievalError(f"Cloud Mail genToken 失败: {result}")
        token = (result.get("data") or {}).get("token")
        if not token:
            raise PinRetrievalError(f"Cloud Mail genToken 返回缺少 token: {result}")
        return token

    def _cloud_mail_search_pin(self, base_url: str, token: str) -> str | None:
        """通过 emailList 接口搜索续约专用的 PIN 邮件并提取 PIN 码。

        服务器端 subject 过滤不可靠（精确匹配报 500），因此在客户端
        按续约邮件专属主题做精确过滤，并只保留最新的一封，避免取到
        Email Validation 等其他 PIN 邮件。
        """
        payload = {
            "toEmail": self.username,
            "sendEmail": "no-reply@euserv.com",
            "type": 0,
            "timeSort": "desc",
            "num": 1,
            "size": 50,
        }
        resp = requests.post(
            f"{base_url}/api/public/emailList",
            json=payload,
            headers={"Authorization": token},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        result = resp.json()
        if not isinstance(result, dict) or result.get("code") != 200:
            raise PinRetrievalError(f"Cloud Mail emailList 失败: {result}")
        emails = result.get("data") or []
        if not isinstance(emails, list):
            raise PinRetrievalError(f"Cloud Mail emailList data 格式异常: {result}")

        renewal_key = "PIN for the Confirmation of a Security Check"
        candidate: dict | None = None
        for email_item in emails:
            if not isinstance(email_item, dict):
                continue
            subject = email_item.get("subject") or ""
            if renewal_key.lower() not in subject.lower():
                continue
            # 时间倒序返回，第一封即为最新；若无 createTime 兜底用 emailId 判断
            if candidate is None:
                candidate = email_item
                continue
            candidate_time = str(candidate.get("createTime") or "9999-99-99 99:99:99")
            current_time = str(email_item.get("createTime") or "9999-99-99 99:99:99")
            if current_time > candidate_time:
                candidate = email_item

        if candidate is None:
            return None
        body = candidate.get("text") or candidate.get("content") or ""
        return self._extract_pin_from_text(body)

    def _get_pin_from_cloud_mail(self) -> str:
        """从 Cloud Mail API 获取 PIN 码（用于无 IMAP 协议的邮箱）。"""
        base_url = self.cloud_mail_api_url.rstrip("/")
        self.log(f"正在通过 Cloud Mail API 获取PIN码 ({base_url})...")

        last_error: Exception | None = None
        for i in range(EMAIL_MAX_RETRIES):
            try:
                token = self._cloud_mail_get_token(base_url)
                pin = self._cloud_mail_search_pin(base_url, token)
                if pin:
                    self.log(f"成功从Cloud Mail获取PIN码: ****{str(pin)[-2:]}")  # type: ignore[index]
                    return pin
                self.log(f"第{i + 1}次尝试：未找到PIN邮件，等待{EMAIL_CHECK_INTERVAL}秒...")
                time.sleep(EMAIL_CHECK_INTERVAL)
            except (requests.RequestException, PinRetrievalError, ValueError) as e:
                last_error = e
                self.log(f"获取PIN码时发生错误 (尝试 {i + 1}/{EMAIL_MAX_RETRIES}): {e}")
                if i < EMAIL_MAX_RETRIES - 1:
                    self.log(f"将在 {EMAIL_CHECK_INTERVAL} 秒后重试...")
                    time.sleep(EMAIL_CHECK_INTERVAL)
        if last_error is not None:
            raise PinRetrievalError(f"Cloud Mail 连接错误: {last_error}") from last_error
        raise PinRetrievalError("多次尝试后仍无法获取PIN码邮件。")

    def _get_pin(self) -> str:
        """根据配置选择 PIN 获取方式。"""
        if self.cloud_mail_api_url:
            return self._get_pin_from_cloud_mail()
        return self._get_pin_from_gmail()

    # ==================== 服务器列表 ====================

    def _parse_server_row(self, tr) -> dict | None:
        """解析单行 <tr> 元素，返回服务器信息字典，无效行返回 None。"""
        server_id_tag = tr.select_one(".td-z1-sp1-kc")
        if not server_id_tag:
            return None
        server_id = server_id_tag.get_text(strip=True)
        action_container = tr.select_one(".td-z1-sp2-kc .kc2_order_action_container")
        if not action_container:
            return None
        action_text = action_container.get_text()
        if RENEWAL_DATE_PATTERN in action_text:
            renewal_date_match = re.search(r"\d{4}-\d{2}-\d{2}", action_text)
            renewal_date = (
                renewal_date_match.group(0) if renewal_date_match else "未知日期"
            )
            return {"id": server_id, "renewable": False, "date": renewal_date}
        return {"id": server_id, "renewable": True, "date": None}

    def _get_servers(self) -> list[dict]:
        """获取服务器列表及其续约状态"""
        self.log("正在访问服务器列表页面...")
        url = f"{EUSERV_BASE_URL}?sess_id={self.sess_id}"
        headers = {"user-agent": USER_AGENT}
        f = self.session.get(url=url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        f.raise_for_status()
        soup = BeautifulSoup(f.text, "html.parser")
        selector = "#kc2_order_customer_orders_tab_content_1 .kc2_order_table.kc2_content_table tr, #kc2_order_customer_orders_tab_content_2 .kc2_order_table.kc2_content_table tr"
        matched_rows = soup.select(selector)
        server_list = [
            s for s in (self._parse_server_row(tr) for tr in matched_rows) if s is not None
        ]
        self.log(f"发现 {len(server_list)} 台服务器合同")

        if not server_list:
            self.log(
                "⚠️ 未能从页面解析出任何服务器信息，可能是页面结构变化！",
                LogLevel.WARNING,
            )
            # 保存 HTML 用于离线调试
            try:
                with open("debug_page.html", "w", encoding="utf-8") as debug_f:
                    debug_f.write(f.text)
                self.log("已保存页面 HTML 到 debug_page.html", LogLevel.INFO)
            except OSError as e:
                self.log(f"保存调试页面失败: {e}", LogLevel.WARNING)

        return server_list

    # ==================== 续期流程 ====================

    def _renew(self, order_id: str) -> None:
        """执行服务器续约流程"""
        self.log(f"正在为服务器 {order_id} 触发续订流程...")
        url = EUSERV_BASE_URL
        headers = {
            "user-agent": USER_AGENT,
            "Host": "support.euserv.com",
            "origin": EUSERV_ORIGIN,
        }
        data1 = {
            "Submit": "Extend contract",
            "sess_id": self.sess_id,
            "ord_no": order_id,
            "subaction": "choose_order",
            "choose_order_subaction": "show_contract_details",
        }
        step1 = self.session.post(
            url, headers=headers, data=data1, timeout=HTTP_TIMEOUT_SECONDS
        )
        step1.raise_for_status()
        data2 = {
            "sess_id": self.sess_id,
            "subaction": "show_kc2_security_password_dialog",
            "prefix": "kc2_customer_contract_details_extend_contract_",
            "type": "1",
        }
        step2 = self.session.post(
            url, headers=headers, data=data2, timeout=HTTP_TIMEOUT_SECONDS
        )
        step2.raise_for_status()
        time.sleep(PIN_WAIT_SECONDS)
        pin = self._get_pin()
        data3 = {
            "auth": pin,
            "sess_id": self.sess_id,
            "subaction": "kc2_security_password_get_token",
            "prefix": "kc2_customer_contract_details_extend_contract_",
            "type": 1,
            "ident": f"kc2_customer_contract_details_extend_contract_{order_id}",
        }
        f = self.session.post(
            url, headers=headers, data=data3, timeout=HTTP_TIMEOUT_SECONDS
        )
        f.raise_for_status()
        response_json = f.json()
        if response_json.get("rs") != "success":
            raise RenewalError(f"获取Token失败: {f.text}")
        token = response_json["token"]["value"]
        self.log("成功获取续期Token")
        data4 = {
            "sess_id": self.sess_id,
            "ord_id": order_id,
            "subaction": "kc2_customer_contract_details_extend_contract_term",
            "token": token,
        }
        final_res = self.session.post(
            url, headers=headers, data=data4, timeout=HTTP_TIMEOUT_SECONDS
        )
        final_res.raise_for_status()

    # ==================== 续期后检查 ====================

    def _log_non_renewable_servers(self, all_servers: list) -> None:
        """记录无需续期的服务器信息并输出下次续约日期。"""
        self.log("检测到所有服务器均无需续期。详情如下：", LogLevel.SUCCESS)
        earliest_date = None
        for server in all_servers:
            if not server["renewable"]:
                self.log(f"   - 服务器 {server['id']}: 可续约日期为 {server['date']}")
                if server["date"] and server["date"] != "未知日期":
                    if earliest_date is None or server["date"] < earliest_date:
                        earliest_date = server["date"]

        if earliest_date and GITHUB_OUTPUT:
            self._output_next_schedule(str(earliest_date))

    def _output_next_schedule(self, date_str: str) -> None:
        """输出下次续约日期的 cron 表达式到 GITHUB_OUTPUT。"""
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                _, month, day = parts
                cron_expr = f"0 0 {int(day)} {int(month)} *"
                self.log(f"📅 下次续约日期: {date_str}", LogLevel.INFO)
                self.log(f"🔄 设置下次运行 cron: {cron_expr}", LogLevel.INFO)
                self.next_renewal_date = date_str
                if self._write_output and GITHUB_OUTPUT:
                    with open(GITHUB_OUTPUT, "a") as f:
                        f.write(f"next_cron={cron_expr}\n")
                        f.write(f"next_date={date_str}\n")
        except (ValueError, OSError) as e:
            self.log(f"解析续约日期失败: {e}", LogLevel.WARNING)

    def _process_server_renewals(self, servers_to_renew: list) -> bool:
        """处理服务器续期，返回是否全部成功。"""
        self.log(
            f"🔍 检测到 {len(servers_to_renew)} 台服务器需要续期: {[s['id'] for s in servers_to_renew]}"
        )
        all_success = True
        for server in servers_to_renew:
            self.log(f"\n🔄 --- 正在为服务器 {server['id']} 执行续期 ---")
            try:
                self._renew(server["id"])
                self.log(
                    f"服务器 {server['id']} 的续期流程已成功提交。", LogLevel.SUCCESS
                )
            except (RenewalError, requests.RequestException) as e:
                self.log(
                    f"为服务器 {server['id']} 续期时发生严重错误: {e}", LogLevel.ERROR
                )
                all_success = False
        return all_success

    def _check_post_renewal_status(self) -> None:
        """检查续期后的服务器状态，并显示下次续约日期。"""
        time.sleep(POST_RENEWAL_CHECK_DELAY)
        server_list = self._fetch_server_list_with_retry()
        servers_still_to_renew = [sv["id"] for sv in server_list if sv["renewable"]]

        if servers_still_to_renew:
            for server_id in servers_still_to_renew:
                self.log(
                    f"警告: 服务器 {server_id} 在续期操作后仍显示为可续约状态。",
                    LogLevel.WARNING,
                )
        else:
            self.log("所有服务器均已成功续订或无需续订！", LogLevel.CELEBRATION)

        # 无论续约状态如何，都尝试输出下次续约日期
        self._display_next_renewal_dates(server_list)

    def _fetch_server_list_with_retry(self) -> list[dict]:
        """获取服务器列表，如果没有日期则重试一次。"""
        server_list = self._get_servers()
        has_valid_date = any(s["date"] and s["date"] != "未知日期" for s in server_list)
        if not has_valid_date:
            self.log(f"首次读取未获取到续约日期，等待 {SERVER_LIST_RETRY_DELAY} 秒后重试...")
            time.sleep(SERVER_LIST_RETRY_DELAY)
            server_list = self._get_servers()
        return server_list

    def _display_next_renewal_dates(self, server_list: list[dict]) -> None:
        """显示每台服务器的下次续约日期并输出最早日期。"""
        earliest_date = None
        for server in server_list:
            if server["date"] and server["date"] != "未知日期":
                self.log(f"   - 服务器 {server['id']}: 下次可续约日期 {server['date']}")
                if earliest_date is None or server["date"] < earliest_date:
                    earliest_date = server["date"]

        if earliest_date:
            self.log(f"📅 下次续约窗口开启时间: {earliest_date}", LogLevel.INFO)
            if GITHUB_OUTPUT:
                self._output_next_schedule(str(earliest_date))

    # ==================== 主入口 ====================

    def run(
        self, notify: bool = True, write_output: bool = True
    ) -> int:
        """执行续期任务的主入口。

        Args:
            notify: 是否在结束后发送邮件/Telegram 通知。多账号模式下由外层统一发送。
            write_output: 是否把下次调度日期写入 GITHUB_OUTPUT。多账号模式下统一取最早日期写入。

        Returns:
            EXIT_SUCCESS (0): 续约成功或无需续约
            EXIT_FAILURE (1): 续约失败
            EXIT_SKIPPED (2): 未到续约日期
        """
        self._write_output = write_output
        config_ok, missing = self.validate_config()
        if not config_ok:
            self.log(f"必要的配置未设置: {', '.join(missing)}", LogLevel.ERROR)
            if self.log_messages:
                self.send_status_email("配置错误")
                self.send_telegram_notification("配置错误")
            return EXIT_FAILURE

        status = "成功"
        exit_code = EXIT_SUCCESS
        try:
            self.log(f"--- 开始 EUServ 续期任务 ({self.account_name}) ---")

            # 预加载 OCR 模型，减少首次验证码识别延迟
            self.prewarm_ocr()

            self._perform_login()

            all_servers = self._get_servers()
            servers_to_renew = [server for server in all_servers if server["renewable"]]

            if not all_servers:
                self.log(
                    "未检测到任何服务器合同，请检查页面是否正常！", LogLevel.WARNING
                )
                status = "异常"
                exit_code = EXIT_FAILURE
                self._safe_refresh_session()
            elif not servers_to_renew:
                # 智能调度：未到续约日期，跳过执行
                self._log_non_renewable_servers(all_servers)
                self.log("ℹ️ 未到续约日期，跳过执行。", LogLevel.INFO)
                status = "跳过"
                exit_code = EXIT_SKIPPED
                self._safe_refresh_session()
            else:
                if not self._process_server_renewals(servers_to_renew):
                    status = "失败"
                    exit_code = EXIT_FAILURE
                self._safe_refresh_session()

            self._check_post_renewal_status()
            self.log("\n🏁 --- 所有工作完成 ---")

        except (LoginError, RenewalError, PinRetrievalError, CaptchaError) as e:
            status = "失败"
            exit_code = EXIT_FAILURE
            self.log(f"❗ 脚本执行过程中发生致命错误: {e}")
        finally:
            self._cleanup()  # 关闭 HTTP Session
            if notify:
                self.send_status_email(status)
                self.send_telegram_notification(status)

        return exit_code


def _run_single() -> int:
    """单账号运行（未配置 EUSERV_ACCOUNTS 时的向后兼容路径）。"""
    bot = RenewalBot()
    return bot.run()


def _run_multi(accounts: list[dict]) -> int:
    """多账号运行：逐个账号执行，最后统一汇总日志与调度、发送一份通知。"""
    results: list[tuple[RenewalBot, int]] = []
    overall = EXIT_SUCCESS
    for acct in accounts:
        bot = RenewalBot(account=acct)
        code = bot.run(notify=False, write_output=False)
        results.append((bot, code))
        if code != EXIT_SUCCESS:
            overall = code  # 任一失败则整体失败（EXIT_FAILURE 优先于跳过）

    # 汇总日志到报告机器人
    report_bot = RenewalBot()
    report_bot.log(f"===== 多账号运行报告（共 {len(accounts)} 个账号）=====")
    report_bot.log(f"{'账号':<24} ｜ {'状态':<6} ｜ 结果")
    for bot, code in results:
        report_bot.log(
            f"{bot.account_name:<24} ｜ {code:<6} ｜ "
            f"{'成功' if code == EXIT_SUCCESS else ('跳过' if code == EXIT_SKIPPED else '失败')}"
        )

    # 汇总日志：按账号分段
    for bot, code in results:
        report_bot.log(f"\n---------- 账号【{bot.account_name}】日志 ----------")
        for idx, line in enumerate(bot.log_messages, start=1):
            report_bot.log(f"{idx}. {line}")

    # 调度：取所有账号中最早的可续约日期写入 GITHUB_OUTPUT 一次
    earliest: str | None = None
    for bot, _code in results:
        if bot.next_renewal_date and (
            earliest is None or bot.next_renewal_date < earliest
        ):
            earliest = bot.next_renewal_date
    if earliest:
        report_bot._output_next_schedule(earliest)

    status = {
        EXIT_FAILURE: "失败",
        EXIT_SUCCESS: "成功",
        EXIT_SKIPPED: "跳过",
    }[overall]
    report_bot.send_status_email(status)
    report_bot.send_telegram_notification(status)
    return overall


def main() -> None:
    """入口点：支持单账号（环境变量）与多账号（逗号分隔）。"""
    try:
        accounts = parse_accounts()
    except ValueError as e:
        print(f"❌ {e}")
        exit(EXIT_FAILURE)

    if accounts:
        exit_code = _run_multi(accounts)
    else:
        exit_code = _run_single()
    exit(exit_code)


if __name__ == "__main__":
    main()
