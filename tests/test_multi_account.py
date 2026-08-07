# Tests for multi-account support (comma-separated credentials)
from unittest.mock import Mock, patch

import Euserv_Renewal as er


class TestParseAccounts:
    """Test parse_accounts (comma-separated multi-account mode)"""

    def test_empty_when_not_configured(self):
        with patch.object(er, "EUSERV_USERNAME", ""):
            assert er.parse_accounts() == []

    def test_empty_for_single_account(self):
        """不含逗号 = 单账号模式，保持向后兼容走模块级常量。"""
        with patch.object(er, "EUSERV_USERNAME", "user1@example.com"):
            assert er.parse_accounts() == []

    def test_parses_two_accounts(self):
        with patch.object(
            er, "EUSERV_USERNAME", "user1@example.com,user2@example.com"
        ), patch.object(er, "EUSERV_PASSWORD", "pw1,pw2"), patch.object(
            er, "EUSERV_2FA", "KEY1,KEY2"
        ):
            accounts = er.parse_accounts()
        assert len(accounts) == 2
        assert accounts[0]["username"] == "user1@example.com"
        assert accounts[0]["password"] == "pw1"
        assert accounts[0]["two_fa"] == "KEY1"
        assert accounts[1]["username"] == "user2@example.com"
        assert accounts[1]["password"] == "pw2"
        assert accounts[1]["two_fa"] == "KEY2"

    def test_mailbox_credentials_are_zipped(self):
        with patch.object(
            er, "EUSERV_USERNAME", "user1@example.com,user2@example.com"
        ), patch.object(er, "EUSERV_PASSWORD", "pw1,pw2"), patch.object(
            er, "EMAIL_USERNAME", "admin1@mail.example,admin2@mail.example"
        ), patch.object(er, "EMAIL_PASSWORD", "mpw1,mpw2"), patch.object(
            er, "CLOUD_MAIL_API_URL", "https://mail1.example,https://mail2.example"
        ):
            accounts = er.parse_accounts()
        assert accounts[0]["email_username"] == "admin1@mail.example"
        assert accounts[0]["cloud_mail_api_url"] == "https://mail1.example"
        assert accounts[1]["email_username"] == "admin2@mail.example"
        assert accounts[1]["cloud_mail_api_url"] == "https://mail2.example"

    def test_missing_fields_fill_empty(self):
        """数量不足的变量补空，不报错。"""
        with patch.object(
            er, "EUSERV_USERNAME", "user1@example.com,user2@example.com"
        ), patch.object(er, "EUSERV_PASSWORD", "pw1"), patch.object(
            er, "EUSERV_2FA", ""
        ):
            accounts = er.parse_accounts()
        assert accounts[1]["password"] == ""
        assert accounts[0]["two_fa"] == ""
        assert accounts[1]["two_fa"] == ""

    def test_strips_whitespace(self):
        with patch.object(
            er, "EUSERV_USERNAME", " user1@example.com , user2@example.com "
        ), patch.object(er, "EUSERV_PASSWORD", " pw1 , pw2 "):
            accounts = er.parse_accounts()
        assert accounts[0]["username"] == "user1@example.com"
        assert accounts[1]["password"] == "pw2"

    def test_name_is_username(self):
        with patch.object(
            er, "EUSERV_USERNAME", "user1@example.com,user2@example.com"
        ), patch.object(er, "EUSERV_PASSWORD", "pw1,pw2"):
            accounts = er.parse_accounts()
        assert accounts[0]["name"] == "user1@example.com"


class TestMultiAccountBot:
    """Test RenewalBot with per-account credentials"""

    def _acct(self):
        return {
            "name": "user1@example.com",
            "username": "user1@example.com",
            "password": "pw1",
            "two_fa": "KEY1",
            "email_host": "",
            "email_username": "admin1@mail.example",
            "email_password": "mpw1",
            "cloud_mail_api_url": "https://mail1.example",
        }

    def test_uses_account_credentials(self):
        bot = er.RenewalBot(account=self._acct())
        assert bot.username == "user1@example.com"
        assert bot.password == "pw1"
        assert bot.two_fa == "KEY1"
        assert bot.email_username == "admin1@mail.example"
        assert bot.cloud_mail_api_url == "https://mail1.example"
        assert bot.account_name == "user1@example.com"

    def test_two_bots_have_independent_credentials(self):
        bot_a = er.RenewalBot(account=self._acct())
        acct_b = self._acct()
        acct_b.update(
            {
                "username": "user2@example.com",
                "email_username": "admin2@mail.example",
                "cloud_mail_api_url": "https://mail2.example",
            }
        )
        bot_b = er.RenewalBot(account=acct_b)
        assert bot_a.username == "user1@example.com"
        assert bot_b.username == "user2@example.com"
        assert bot_a.cloud_mail_api_url != bot_b.cloud_mail_api_url
        assert bot_a.email_username != bot_b.email_username

    def test_validate_config_checks_account(self):
        acct = self._acct()
        acct["email_password"] = ""
        bot = er.RenewalBot(account=acct)
        ok, missing = bot.validate_config()
        assert not ok
        assert "EMAIL_PASSWORD" in missing

    def test_validate_config_ok_for_cloud_mail_account(self):
        bot = er.RenewalBot(account=self._acct())
        ok, missing = bot.validate_config()
        assert ok
        assert missing == []

    def test_validate_config_requires_email_host_for_imap_account(self):
        acct = self._acct()
        acct["cloud_mail_api_url"] = ""
        acct["email_host"] = ""
        bot = er.RenewalBot(account=acct)
        ok, missing = bot.validate_config()
        assert not ok
        assert "EMAIL_HOST" in missing

    @patch.object(er.requests, "post")
    def test_cloud_mail_uses_account_admin_creds(self, mock_post):
        mock_post.side_effect = [
            Mock(
                raise_for_status=Mock(return_value=None),
                json=Mock(
                    return_value={
                        "code": 200,
                        "data": {"token": "tok"},
                    }
                ),
            ),
            Mock(
                raise_for_status=Mock(return_value=None),
                json=Mock(
                    return_value={
                        "code": 200,
                        "data": [
                            {
                                "sendEmail": "no-reply@euserv.com",
                                "subject": "EUserv - PIN for the Confirmation of a Security Check",
                                "text": "PIN: 123456",
                            }
                        ],
                    }
                ),
            ),
        ]
        bot = er.RenewalBot(account=self._acct())
        pin = bot._get_pin_from_cloud_mail()
        assert pin == "123456"
        token_call = mock_post.call_args_list[0]
        assert token_call.kwargs["json"] == {
            "email": "admin1@mail.example",
            "password": "mpw1",
        }
        list_call = mock_post.call_args_list[1]
        assert list_call.kwargs["json"]["toEmail"] == "user1@example.com"


class TestMultiAccountOrchestration:
    """Test _run_multi aggregation"""

    @patch.object(er.RenewalBot, "run")
    @patch.object(er.RenewalBot, "send_status_email")
    @patch.object(er.RenewalBot, "send_telegram_notification")
    def test_run_multi_returns_failure_when_any_fails(
        self, mock_tg, mock_email, mock_run
    ):
        mock_run.side_effect = [er.EXIT_SUCCESS, er.EXIT_FAILURE]
        accounts = [
            {"username": "user1@example.com", "password": "pw1"},
            {"username": "user2@example.com", "password": "pw2"},
        ]
        code = er._run_multi(accounts)
        assert code == er.EXIT_FAILURE
        assert mock_run.call_count == 2
        mock_email.assert_called_once()
        mock_tg.assert_called_once()

    @patch.object(er.RenewalBot, "run")
    @patch.object(er.RenewalBot, "send_status_email")
    @patch.object(er.RenewalBot, "send_telegram_notification")
    def test_run_multi_skip_when_all_skip(self, mock_tg, mock_email, mock_run):
        mock_run.side_effect = [er.EXIT_SKIPPED, er.EXIT_SKIPPED]
        accounts = [
            {"username": "user1@example.com", "password": "pw1"},
            {"username": "user2@example.com", "password": "pw2"},
        ]
        code = er._run_multi(accounts)
        assert code == er.EXIT_SKIPPED
        mock_email.assert_called_once_with("跳过")
        mock_tg.assert_called_once_with("跳过")

    @patch.object(er.RenewalBot, "run")
    @patch.object(er.RenewalBot, "send_status_email")
    @patch.object(er.RenewalBot, "send_telegram_notification")
    def test_run_multi_success_when_all_success(self, mock_tg, mock_email, mock_run):
        mock_run.side_effect = [er.EXIT_SUCCESS, er.EXIT_SUCCESS]
        accounts = [
            {"username": "user1@example.com", "password": "pw1"},
            {"username": "user2@example.com", "password": "pw2"},
        ]
        code = er._run_multi(accounts)
        assert code == er.EXIT_SUCCESS
        mock_email.assert_called_once_with("成功")
        mock_tg.assert_called_once_with("成功")

    @patch.object(er.RenewalBot, "run")
    def test_run_multi_runs_without_notify_and_output(self, mock_run):
        mock_run.return_value = er.EXIT_SUCCESS
        accounts = [
            {"username": "user1@example.com", "password": "pw1"},
            {"username": "user2@example.com", "password": "pw2"},
        ]
        er._run_multi(accounts)
        for call in mock_run.call_args_list:
            assert call.kwargs["notify"] is False
            assert call.kwargs["write_output"] is False

    @patch.object(er.RenewalBot, "run", autospec=True)
    @patch.object(er.RenewalBot, "send_status_email")
    @patch.object(er.RenewalBot, "send_telegram_notification")
    def test_run_multi_uses_earliest_renewal_date(
        self, mock_tg, mock_email, mock_run
    ):
        dates = iter(["2026-09-01", "2026-08-15"])

        def _fake_run(self, *args, **kwargs):
            self.next_renewal_date = next(dates)
            return er.EXIT_SUCCESS

        mock_run.side_effect = _fake_run
        with patch.object(er.RenewalBot, "_output_next_schedule") as mock_output:
            er._run_multi(
                [
                    {"username": "user1@example.com", "password": "pw1"},
                    {"username": "user2@example.com", "password": "pw2"},
                ]
            )
            mock_output.assert_called_once_with("2026-08-15")
