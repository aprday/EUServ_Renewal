from datetime import date

import json

from euserv_renew import (
    parse_contract_status,
    private_label,
    read_renewal_state,
    redact_sensitive,
    renewal_due_date_reached,
    write_renewal_state,
)
from euserv_renew import AccountConfig, EUserv, TimeoutSession


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


def test_stop_date_comes_from_contract_due_date():
    assert not renewal_due_date_reached("2026-09-09", today=date(2026, 9, 8))
    assert renewal_due_date_reached("2026-09-09", today=date(2026, 9, 9))
    assert renewal_due_date_reached("2026-09-09", today=date(2026, 9, 10))


def _load_repair_module():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "tools" / "repair_state.py"
    spec = importlib.util.spec_from_file_location("repair_state", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repair_state_fixes_corrupted_file(tmp_path, monkeypatch):
    module = _load_repair_module()
    state_file = tmp_path / "renewal_state.json"
    state_file.write_text(
        '{\\"next_renewal_date\\":\\"2026-10-09\\"}', encoding="utf-8"
    )
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    assert module.main() == 0

    repaired = json.loads(state_file.read_text(encoding="utf-8"))
    assert repaired["status"] == "waiting"
    assert repaired["next_renewal_date"] == ""
    assert list(tmp_path.glob("renewal_state.broken-*.json"))


def test_repair_state_leaves_valid_file_untouched(tmp_path, monkeypatch):
    module = _load_repair_module()
    state_file = tmp_path / "renewal_state.json"
    state_file.write_text(
        json.dumps({"next_renewal_date": "2026-11-09", "status": "waiting"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STATE_FILE", state_file)

    assert module.main() == 0

    kept = json.loads(state_file.read_text(encoding="utf-8"))
    assert kept["next_renewal_date"] == "2026-11-09"
    assert not list(tmp_path.glob("renewal_state.broken-*.json"))


def test_euserv_session_has_default_timeout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = EUserv(AccountConfig("user@example.com", "secret"))

    assert isinstance(client.session, TimeoutSession)


def test_read_renewal_state_survives_corrupted_json(tmp_path, monkeypatch):
    state_file = tmp_path / "renewal_state.json"
    state_file.write_text(
        '{\\"next_renewal_date\\":\\"2026-10-09\\"}', encoding="utf-8"
    )
    monkeypatch.setattr("euserv_renew.RENEWAL_STATE_FILE", str(state_file))

    assert read_renewal_state() == {}


def test_read_renewal_state_returns_valid_dict(tmp_path, monkeypatch):
    state_file = tmp_path / "renewal_state.json"
    state_file.write_text(
        json.dumps({"next_renewal_date": "2026-11-09", "status": "waiting"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("euserv_renew.RENEWAL_STATE_FILE", str(state_file))

    assert read_renewal_state()["next_renewal_date"] == "2026-11-09"
