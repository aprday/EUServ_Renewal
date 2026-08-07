# Tests for parallel CAPTCHA solving (local OCR + TrueCaptcha API)
import pytest
from unittest.mock import patch

import Euserv_Renewal as er


class TestSolveCaptcha:
    """Test _solve_captcha parallel dual-channel logic"""

    def _bot(self):
        return er.RenewalBot()

    def test_local_only_when_api_unconfigured(self):
        bot = self._bot()
        with patch.object(er, "CAPTCHA_USERID", ""), patch.object(
            er, "CAPTCHA_APIKEY", ""
        ), patch.object(bot, "_solve_captcha_local", return_value="42"):
            assert bot._solve_captcha(b"img") == "42"

    def test_local_only_raises_when_no_result(self):
        bot = self._bot()
        with patch.object(er, "CAPTCHA_USERID", ""), patch.object(
            er, "CAPTCHA_APIKEY", ""
        ), patch.object(bot, "_solve_captcha_local", return_value=None):
            with pytest.raises(er.CaptchaError):
                bot._solve_captcha(b"img")

    def test_api_wins_when_local_fails(self):
        bot = self._bot()
        with patch.object(er, "CAPTCHA_USERID", "uid"), patch.object(
            er, "CAPTCHA_APIKEY", "key"
        ), patch.object(bot, "_solve_captcha_local", return_value=None), patch.object(
            bot, "_solve_captcha_api", return_value="123"
        ):
            assert bot._solve_captcha(b"img") == "123"

    def test_local_wins_when_api_fails(self):
        bot = self._bot()
        with patch.object(er, "CAPTCHA_USERID", "uid"), patch.object(
            er, "CAPTCHA_APIKEY", "key"
        ), patch.object(bot, "_solve_captcha_local", return_value="777"), patch.object(
            bot, "_solve_captcha_api", return_value=None
        ):
            assert bot._solve_captcha(b"img") == "777"

    def test_raises_when_both_fail(self):
        bot = self._bot()
        with patch.object(er, "CAPTCHA_USERID", "uid"), patch.object(
            er, "CAPTCHA_APIKEY", "key"
        ), patch.object(bot, "_solve_captcha_local", return_value=None), patch.object(
            bot, "_solve_captcha_api", return_value=None
        ):
            with pytest.raises(er.CaptchaError):
                bot._solve_captcha(b"img")