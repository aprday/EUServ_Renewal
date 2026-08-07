# Tests for Cloud Mail API PIN retrieval
import pytest
from unittest.mock import Mock, patch

import Euserv_Renewal as er


class TestExtractPinFromText:
    """Test _extract_pin_from_text static method"""

    def test_basic_pin(self):
        assert er.RenewalBot._extract_pin_from_text("Your PIN: 123456") == "123456"

    def test_pin_with_newline(self):
        assert er.RenewalBot._extract_pin_from_text("PIN:\n987654") == "987654"

    def test_no_pin(self):
        assert er.RenewalBot._extract_pin_from_text("No pin here") is None

    def test_lowercase_pin(self):
        assert er.RenewalBot._extract_pin_from_text("pin: 000111") == "000111"

    def test_pin_in_html(self):
        body = "<html><body>PIN: 456789</body></html>"
        assert er.RenewalBot._extract_pin_from_text(body) == "456789"


class TestCloudMailPin:
    """Test Cloud Mail API PIN retrieval"""

    def _mock_response(self, payload: dict):
        resp = Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = payload
        return resp

    @patch.object(er.requests, "post")
    def test_get_token_success(self, mock_post):
        mock_post.return_value = self._mock_response(
            {"code": 200, "message": "success", "data": {"token": "abc123"}}
        )
        bot = er.RenewalBot()
        token = bot._cloud_mail_get_token("https://mail.example.com")
        assert token == "abc123"

    @patch.object(er.requests, "post")
    def test_get_token_failure(self, mock_post):
        mock_post.return_value = self._mock_response(
            {"code": 401, "message": "unauthorized"}
        )
        bot = er.RenewalBot()
        with pytest.raises(er.PinRetrievalError):
            bot._cloud_mail_get_token("https://mail.example.com")

    @patch.object(er.requests, "post")
    def test_search_pin_success(self, mock_post):
        mock_post.return_value = self._mock_response(
            {
                "code": 200,
                "message": "success",
                "data": [
                    {
                        "emailId": 1,
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for the Confirmation of a Security Check",
                        "text": "PIN: 654321",
                        "type": 0,
                    }
                ],
            }
        )
        bot = er.RenewalBot()
        pin = bot._cloud_mail_search_pin("https://mail.example.com", "token")
        assert pin == "654321"

    @patch.object(er.requests, "post")
    def test_search_pin_from_html_content(self, mock_post):
        mock_post.return_value = self._mock_response(
            {
                "code": 200,
                "message": "success",
                "data": [
                    {
                        "emailId": 1,
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for the Confirmation of a Security Check",
                        "content": "<div>PIN: 111222</div>",
                        "text": "",
                        "type": 0,
                    }
                ],
            }
        )
        bot = er.RenewalBot()
        pin = bot._cloud_mail_search_pin("https://mail.example.com", "token")
        assert pin == "111222"

    @patch.object(er.requests, "post")
    def test_search_pin_not_found(self, mock_post):
        mock_post.return_value = self._mock_response(
            {"code": 200, "message": "success", "data": []}
        )
        bot = er.RenewalBot()
        assert bot._cloud_mail_search_pin("https://mail.example.com", "token") is None

    @patch.object(er.requests, "post")
    def test_search_pin_ignores_non_renewal_subjects(self, mock_post):
        """含有其他 PIN（如 Email Validation）但主题不对，不应被当作续约 PIN。"""
        mock_post.return_value = self._mock_response(
            {
                "code": 200,
                "message": "success",
                "data": [
                    {
                        "emailId": 2,
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for Email Validation",
                        "text": "PIN: 888888",
                        "createTime": "2026-08-07 05:00:00",
                        "type": 0,
                    },
                    {
                        "emailId": 1,
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for the Confirmation of a Security Check",
                        "text": "PIN: 111222",
                        "createTime": "2026-08-07 04:00:00",
                        "type": 0,
                    },
                ],
            }
        )
        bot = er.RenewalBot()
        pin = bot._cloud_mail_search_pin("https://mail.example.com", "token")
        assert pin == "111222"

    @patch.object(er.requests, "post")
    def test_search_pin_takes_latest_when_multiple(self, mock_post):
        """存在多封续约 PIN 邮件时，应取 createTime 最新的一封。"""
        mock_post.return_value = self._mock_response(
            {
                "code": 200,
                "message": "success",
                "data": [
                    {
                        "emailId": 3,
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for the Confirmation of a Security Check",
                        "text": "PIN: 333333",
                        "createTime": "2026-08-07 04:00:00",
                        "type": 0,
                    },
                    {
                        "emailId": 4,
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for the Confirmation of a Security Check",
                        "text": "PIN: 444444",
                        "createTime": "2026-08-07 06:00:00",
                        "type": 0,
                    },
                ],
            }
        )
        bot = er.RenewalBot()
        assert bot._cloud_mail_search_pin("https://mail.example.com", "token") == "444444"

    @patch.object(er.requests, "post")
    def test_get_pin_from_cloud_mail_success(self, mock_post):
        mock_post.side_effect = [
            self._mock_response(
                {"code": 200, "message": "success", "data": {"token": "abc"}}
            ),
            self._mock_response(
                {
                    "code": 200,
                    "message": "success",
                    "data": [{
                        "sendEmail": "no-reply@euserv.com",
                        "subject": "EUserv - PIN for the Confirmation of a Security Check",
                        "text": "PIN: 999888",
                    }],
                }
            ),
        ]
        bot = er.RenewalBot()
        with patch.object(er, "CLOUD_MAIL_API_URL", "https://mail.example.com/"):
            pin = bot._get_pin_from_cloud_mail()
        assert pin == "999888"
