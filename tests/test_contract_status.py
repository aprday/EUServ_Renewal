from datetime import date

from euserv_renew import parse_contract_status


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
