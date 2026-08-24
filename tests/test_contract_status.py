from datetime import date

import json

from euserv_renew import parse_contract_status, write_renewal_state


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

    write_renewal_state("479673", "2027-09-09")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["order_id"] == "479673"
    assert state["next_renewal_date"] == "2027-09-09"
    assert state["status"] == "waiting"
