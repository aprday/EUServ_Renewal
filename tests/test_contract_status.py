from datetime import date

import json

from euserv_renew import (
    parse_contract_status,
    private_label,
    redact_sensitive,
    write_renewal_state,
)


def test_future_renewal_date_is_not_renewable():
    assert parse_contract_status(
        "Contract extension possible from 2026-09-09",
        has_extend_control=False,
        today=date(2026, 8, 24),
    ) == (False, "2026-09-09")


def test_empty_action_is_never_assumed_renewable():
    assert parse_contract_status("", False, today=date(2026, 8, 24)) == (False, "")


def test_explicit_extend_control_allows_renewal():
    assert parse_contract_status(
        "Extend contract", True, today=date(2026, 9, 9)
    ) == (True, "")


def test_due_date_still_requires_explicit_control():
    assert parse_contract_status(
        "Contract extension possible from 2026-09-09",
        has_extend_control=False,
        today=date(2026, 9, 9),
    ) == (False, "2026-09-09")


def test_write_renewal_state(tmp_path, monkeypatch):
    state_file = tmp_path / "renewal_state.json"
    monkeypatch.setattr("euserv_renew.RENEWAL_STATE_FILE", str(state_file))

    write_renewal_state("example-contract", "2027-09-09")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert "order_id" not in state
    assert state["next_renewal_date"] == "2027-09-09"
    assert state["status"] == "waiting"


def test_redact_sensitive_hides_email_and_security_values(monkeypatch):
    monkeypatch.setenv("EUSERV_PASSWORD", "private-password")

    message = redact_sensitive(
        "user@example.com password=private-password PIN: 123456 token=abcdef"
    )

    assert "user@example.com" not in message
    assert "private-password" not in message
    assert "123456" not in message
    assert "abcdef" not in message


def test_private_label_is_stable_and_does_not_reveal_value():
    label = private_label("account", "user@example.com")

    assert label == private_label("account", "user@example.com")
    assert "user" not in label
    assert "example" not in label
