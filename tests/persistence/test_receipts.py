from datetime import datetime, timezone

import pytest

from muster.domain.pricing import CostBreakdown, LineItem
from muster.domain.types import CarveOut, ChangeKind, Money
from muster.persistence.receipts import ReceiptBook

TZ = timezone.utc
AT = datetime(2026, 7, 27, 6, 20, tzinfo=TZ)

BREAKDOWN = CostBreakdown(
    lines=(LineItem("schedule change premium (under_24_hours)", "DCWP example", Money(cents=7500)),),
    total=Money(cents=7500), carve_outs_applied=(), requires_consent=False,
    consent_kind=None, lawful=True, unlawful_reason=None,
)


def _write(book, **overrides):
    args = dict(
        site_id="site-nyc", worker_id="w-nyc-3", shift_id="s-12",
        kind=ChangeKind.ADD_SHIFT, jurisdiction_code="us-ny-nyc-fastfood",
        rulebook_effective_from="2017-11-26", breakdown=BREAKDOWN,
        decided_by="muster", consent=None, at=AT,
    )
    return book.write(**{**args, **overrides})


def test_a_receipt_records_the_clause_and_the_money():
    receipt = _write(ReceiptBook())
    assert receipt.total == Money(cents=7500)
    assert receipt.lines[0].citation == "DCWP example"


def test_a_receipt_names_the_rulebook_version_in_force():
    receipt = _write(ReceiptBook())
    assert receipt.jurisdiction_code == "us-ny-nyc-fastfood"
    assert receipt.rulebook_effective_from == "2017-11-26"


def test_a_receipt_names_who_decided():
    book = ReceiptBook()
    assert _write(book).decided_by == "muster"
    assert _write(book, decided_by="Roger K").decided_by == "Roger K"


def test_a_carve_out_that_was_claimed_is_recorded_with_the_change():
    breakdown = CostBreakdown(
        lines=(), total=Money.zero(), carve_outs_applied=(CarveOut.STANDBY_LIST,),
        requires_consent=False, consent_kind=None, lawful=True, unlawful_reason=None,
    )
    receipt = _write(ReceiptBook(), breakdown=breakdown)
    assert receipt.carve_outs_applied == (CarveOut.STANDBY_LIST,)


def test_receipts_are_append_only():
    receipt = _write(ReceiptBook())
    with pytest.raises(Exception):
        receipt.total = Money.zero()


def test_csv_export_has_one_row_per_receipt_and_a_header():
    book = ReceiptBook()
    _write(book)
    _write(book, shift_id="s-13")
    rows = book.to_csv().strip().splitlines()
    assert len(rows) == 3
    assert rows[0].startswith("at,site_id,worker_id,shift_id")


def test_filtering_by_site_returns_only_that_sites_receipts():
    book = ReceiptBook()
    _write(book, site_id="site-nyc")
    _write(book, site_id="site-chi")
    assert len(book.for_site("site-chi")) == 1
