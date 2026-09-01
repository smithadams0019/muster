from datetime import date

import pytest

from muster.domain.carve_outs import CarveOutClaim, carve_out_applies
from muster.domain.types import CarveOut
from muster.rulebook.loader import for_code

ON = date(2026, 9, 1)
OR_RULES = for_code("us-or", on=ON)
CHI = for_code("us-il-chicago", on=ON)


class FakeEvidence:
    """Records what the world actually knows, which is the whole point."""

    def __init__(self, **facts):
        self.facts = facts

    def worker_requested(self, worker_id, shift_id):
        return self.facts.get("requested", False)

    def on_standby_list(self, worker_id):
        return self.facts.get("on_standby", False)

    def standby_accepted(self, worker_id, shift_id):
        return self.facts.get("standby_accepted", False)

    def trade_accepted_by_both(self, shift_id, from_worker, to_worker):
        return self.facts.get("trade_accepted", False)

    def written_agreement(self, evidence_id):
        return self.facts.get("written_agreement", False)

    def declared_incident(self, evidence_id):
        return self.facts.get("incident")


def _applies(claim, rules=OR_RULES, evidence=None, against_rest=False):
    return carve_out_applies(
        claim, rules=rules, worker_id="w-1", shift_id="s-1",
        evidence=evidence or FakeEvidence(), against_rest=against_rest,
    )


def test_a_claim_the_world_cannot_evidence_does_not_apply():
    """The agent saying 'the worker asked for this' is not the worker asking."""
    assert _applies(CarveOutClaim(CarveOut.WORKER_REQUESTED, None)) is False


def test_a_worker_requested_claim_applies_when_the_request_exists():
    evidence = FakeEvidence(requested=True)
    assert _applies(CarveOutClaim(CarveOut.WORKER_REQUESTED, None), evidence=evidence) is True


def test_standby_needs_both_membership_and_acceptance():
    assert _applies(CarveOutClaim(CarveOut.STANDBY_LIST, None),
                    evidence=FakeEvidence(on_standby=True)) is False
    assert _applies(CarveOutClaim(CarveOut.STANDBY_LIST, None),
                    evidence=FakeEvidence(on_standby=True, standby_accepted=True)) is True


def test_a_carve_out_the_jurisdiction_does_not_offer_never_applies():
    """Chicago has no standby carve-out. Claiming one there is the failure mode."""
    evidence = FakeEvidence(on_standby=True, standby_accepted=True)
    assert _applies(CarveOutClaim(CarveOut.STANDBY_LIST, None), rules=CHI, evidence=evidence) is False


def test_an_act_of_nature_needs_a_declared_incident():
    assert _applies(CarveOutClaim(CarveOut.ACT_OF_NATURE, "inc-1")) is False
    evidence = FakeEvidence(incident=CarveOut.ACT_OF_NATURE)
    assert _applies(CarveOutClaim(CarveOut.ACT_OF_NATURE, "inc-1"), evidence=evidence) is True


def test_a_declared_incident_of_the_wrong_kind_does_not_transfer():
    evidence = FakeEvidence(incident=CarveOut.UTILITY_FAILURE)
    assert _applies(CarveOutClaim(CarveOut.ACT_OF_NATURE, "inc-1"), evidence=evidence) is False


def test_no_carve_out_ever_reaches_a_rest_rule_in_chicago():
    """'Other rights, such as Right to Rest ... have no exceptions.'"""
    evidence = FakeEvidence(requested=True, incident=CarveOut.ACT_OF_NATURE)
    for kind in (CarveOut.WORKER_REQUESTED, CarveOut.ACT_OF_NATURE):
        assert _applies(CarveOutClaim(kind, "inc-1"), rules=CHI,
                        evidence=evidence, against_rest=True) is False


def test_oregon_rest_can_be_carved_out_by_the_workers_own_request():
    evidence = FakeEvidence(requested=True)
    assert _applies(CarveOutClaim(CarveOut.WORKER_REQUESTED, None),
                    rules=OR_RULES, evidence=evidence, against_rest=True) is True


def test_an_unrecognised_claim_raises_rather_than_passing_quietly():
    with pytest.raises(ValueError, match="unrecognised"):
        carve_out_applies(
            CarveOutClaim("free_shipping", None), rules=OR_RULES,   # type: ignore[arg-type]
            worker_id="w-1", shift_id="s-1", evidence=FakeEvidence(),
        )
