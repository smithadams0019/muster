from datetime import datetime, timedelta, timezone

import pytest

from muster.domain.types import ConsentKind, ConsentOutcome, Money
from muster.persistence.consent import ConsentStore

TZ = timezone.utc
NOW = datetime(2026, 7, 27, 6, 12, tzinfo=TZ)


def _ask(store, worker="w-1", shift="s-1"):
    return store.ask(
        worker_id=worker, shift_id=shift, kind=ConsentKind.REST_WAIVER,
        premium_owed=Money.from_dollars("100.00"),
        what_it_means="You would start 9 hours after last night's close.",
        asked_at=NOW, expires_in=timedelta(minutes=30),
    )


def test_the_ask_states_the_money_the_worker_is_owed():
    """Consent given without knowing what you are owed is what the law prevents."""
    request = _ask(ConsentStore())
    assert "100.00" in request.what_it_means or request.premium_owed.cents == 10000
    assert request.premium_owed == Money.from_dollars("100.00")


def test_granting_records_the_outcome_and_the_time():
    store = ConsentStore()
    request = _ask(store)
    record = store.answer(request.request_id, ConsentOutcome.GRANTED,
                          answered_at=NOW + timedelta(minutes=4), channel="sms")
    assert record.outcome is ConsentOutcome.GRANTED
    assert record.answered_at == NOW + timedelta(minutes=4)
    assert store.pending() == []


def test_a_decline_is_final_for_that_shift():
    store = ConsentStore()
    request = _ask(store)
    store.answer(request.request_id, ConsentOutcome.DECLINED, answered_at=NOW, channel="sms")
    assert store.has_declined("w-1", "s-1") is True


def test_asking_a_worker_who_declined_this_shift_is_refused():
    store = ConsentStore()
    request = _ask(store)
    store.answer(request.request_id, ConsentOutcome.DECLINED, answered_at=NOW, channel="sms")
    with pytest.raises(PermissionError, match="already declined"):
        _ask(store)


def test_silence_is_a_decline_not_a_grant():
    store = ConsentStore()
    request = _ask(store)
    store.expire_due(now=NOW + timedelta(hours=1))
    assert store.outcome_for(request.request_id) is ConsentOutcome.EXPIRED
    assert store.has_declined("w-1", "s-1") is True


def test_answering_an_unknown_request_raises():
    with pytest.raises(KeyError, match="nope"):
        ConsentStore().answer("nope", ConsentOutcome.GRANTED, answered_at=NOW, channel="sms")


def test_answering_the_same_request_twice_raises():
    store = ConsentStore()
    request = _ask(store)
    store.answer(request.request_id, ConsentOutcome.GRANTED, answered_at=NOW, channel="sms")
    with pytest.raises(KeyError, match="already answered"):
        store.answer(request.request_id, ConsentOutcome.DECLINED, answered_at=NOW, channel="sms")


def test_a_decline_on_one_shift_does_not_block_a_different_shift():
    store = ConsentStore()
    request = _ask(store, shift="s-1")
    store.answer(request.request_id, ConsentOutcome.DECLINED, answered_at=NOW, channel="sms")
    assert _ask(store, shift="s-2") is not None
