# Tests for Telegram Bot notification
import pytest
from unittest.mock import Mock, patch

import Euserv_Renewal as er


class TestTelegramNotification:
    """Test send_telegram_notification method"""

    def _mock_response(self):
        resp = Mock()
        resp.raise_for_status.return_value = None
        return resp

    def test_skips_when_not_configured(self):
        bot = er.RenewalBot()
        with patch.object(er, "TG_BOT_TOKEN", ""), patch.object(
            er, "TG_USER_ID", ""
        ), patch.object(er.requests, "post") as mock_post:
            bot.send_telegram_notification("成功")
            mock_post.assert_not_called()

    def test_sends_successfully(self):
        bot = er.RenewalBot()
        bot.log("登录成功")
        bot.log("续约完成")
        with patch.object(er, "TG_BOT_TOKEN", "123:abc"), patch.object(
            er, "TG_USER_ID", "456"
        ), patch.object(er, "TG_API_HOST", "https://api.telegram.org"), patch.object(
            er.requests, "post", return_value=self._mock_response()
        ) as mock_post:
            bot.send_telegram_notification("成功")
        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        assert kwargs["data"]["chat_id"] == "456"
        assert kwargs["data"]["text"].startswith(
            "<b>📋 EUServ 续期脚本运行报告 — 成功</b>"
        )
        assert "登录成功" in kwargs["data"]["text"]
        assert kwargs["data"]["parse_mode"] == "HTML"

    def test_logs_error_on_failure(self):
        bot = er.RenewalBot()
        resp = Mock()
        resp.raise_for_status.side_effect = er.requests.RequestException("boom")
        with patch.object(er, "TG_BOT_TOKEN", "123:abc"), patch.object(
            er, "TG_USER_ID", "456"
        ), patch.object(er.requests, "post", return_value=resp):
            bot.send_telegram_notification("成功")
        assert any("Telegram 推送失败" in msg for msg in bot.log_messages)

    def test_truncates_long_logs(self):
        bot = er.RenewalBot()
        for i in range(200):
            bot.log(f"日志第 {i} 行")
        with patch.object(er, "TG_BOT_TOKEN", "123:abc"), patch.object(
            er, "TG_USER_ID", "456"
        ), patch.object(er.requests, "post", return_value=self._mock_response()) as mock_post:
            bot.send_telegram_notification("成功")
        text = mock_post.call_args.kwargs["data"]["text"]
        assert len(text) <= 4096
        assert "已截断" in text