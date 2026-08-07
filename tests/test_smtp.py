# Tests for SMTP email notification
from unittest.mock import MagicMock, patch

import Euserv_Renewal as er


class TestSendStatusEmail:
    """Test send_status_email method"""

    def _mock_smtp(self):
        server = MagicMock()
        return server

    def test_skips_when_notification_email_missing(self):
        bot = er.RenewalBot()
        with patch.object(er, "NOTIFICATION_EMAIL", ""), patch.object(
            er, "SMTP_USERNAME", "smtp@example.com"
        ), patch.object(er, "SMTP_PASSWORD", "pw"), patch.object(
            er, "SMTP_HOST", "smtp.example.com"
        ), patch.object(er.smtplib, "SMTP") as mock_smtp:
            bot.send_status_email("成功")
            mock_smtp.assert_not_called()
        assert any("跳过发送邮件" in msg for msg in bot.log_messages)

    def test_skips_when_credentials_missing(self):
        bot = er.RenewalBot()
        with patch.object(er, "NOTIFICATION_EMAIL", "to@example.com"), patch.object(
            er, "SMTP_USERNAME", ""
        ), patch.object(er, "SMTP_PASSWORD", ""), patch.object(
            er, "SMTP_HOST", "smtp.example.com"
        ), patch.object(er.smtplib, "SMTP") as mock_smtp:
            bot.send_status_email("成功")
            mock_smtp.assert_not_called()
        assert any("跳过发送邮件" in msg for msg in bot.log_messages)

    def test_skips_when_smtp_host_missing(self):
        bot = er.RenewalBot()
        with patch.object(er, "NOTIFICATION_EMAIL", "to@example.com"), patch.object(
            er, "SMTP_USERNAME", "smtp@example.com"
        ), patch.object(er, "SMTP_PASSWORD", "pw"), patch.object(
            er, "SMTP_HOST", ""
        ), patch.object(er.smtplib, "SMTP") as mock_smtp:
            bot.send_status_email("成功")
            mock_smtp.assert_not_called()
        assert any("无法推断 SMTP 服务器地址" in msg for msg in bot.log_messages)

    def test_sends_successfully(self):
        bot = er.RenewalBot()
        bot.log("登录成功")
        with patch.object(er, "NOTIFICATION_EMAIL", "to@example.com"), patch.object(
            er, "SMTP_USERNAME", "smtp@example.com"
        ), patch.object(er, "SMTP_PASSWORD", "pw"), patch.object(
            er, "SMTP_HOST", "smtp.example.com"
        ), patch.object(er, "SMTP_PORT", 465), patch.object(
            er.smtplib, "SMTP", return_value=self._mock_smtp()
        ) as mock_smtp:
            bot.send_status_email("成功")
        mock_smtp.assert_called_once_with("smtp.example.com", 465, timeout=er.HTTP_TIMEOUT_SECONDS)
        server = mock_smtp.return_value
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("smtp@example.com", "pw")
        server.sendmail.assert_called_once()
        args, kwargs = server.sendmail.call_args
        assert args[0] == "smtp@example.com"
        assert args[1] == ["to@example.com"]
        assert any("已成功发送" in msg for msg in bot.log_messages)

    def test_uses_separate_smtp_credentials(self):
        """163 推送场景：SMTP_USERNAME/PASSWORD 与 EMAIL_* 不同，互不干扰。"""
        bot = er.RenewalBot()
        with patch.object(er, "NOTIFICATION_EMAIL", "to@example.com"), patch.object(
            er, "EMAIL_USERNAME", "admin@mail-a.example"
        ), patch.object(er, "EMAIL_PASSWORD", "admin_pw"), patch.object(
            er, "SMTP_USERNAME", "user@163.com"
        ), patch.object(er, "SMTP_PASSWORD", "smtp_auth_code"), patch.object(
            er, "SMTP_HOST", "smtp.163.com"
        ), patch.object(er.smtplib, "SMTP", return_value=self._mock_smtp()) as mock_smtp:
            bot.send_status_email("成功")
        server = mock_smtp.return_value
        server.login.assert_called_once_with("user@163.com", "smtp_auth_code")
