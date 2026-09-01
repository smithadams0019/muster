import pytest

from muster.mcp_server.server import build_server

WRITE_WORDS = ("assign", "post", "cancel", "notify", "consent", "create", "delete", "update")


def _payload(result):
    """`call_tool` in installed mcp 1.29.1 returns (content_list, {"result": ...})."""
    return result[1]["result"] if isinstance(result, tuple) else result


async def test_the_server_exposes_exactly_the_five_read_tools():
    tools = {t.name for t in await build_server().list_tools()}
    assert tools == {
        "list_jurisdictions", "get_rules", "price_schedule_change",
        "check_rest", "audit_schedule",
    }


async def test_no_exposed_tool_can_change_anyones_week():
    """The safety claim, asserted rather than asserted-in-prose."""
    for tool in await build_server().list_tools():
        assert not any(word in tool.name for word in WRITE_WORDS), tool.name


async def test_every_tool_has_a_description_a_stranger_can_act_on():
    for tool in await build_server().list_tools():
        assert tool.description and len(tool.description) > 40, tool.name


async def test_list_jurisdictions_returns_codes_dates_and_citations():
    server = build_server()
    result = await server.call_tool("list_jurisdictions", {})
    payload = _payload(result)
    codes = {row["code"] for row in payload}
    assert "us-il-chicago" in codes
    assert all(row["citation"].startswith("https://") for row in payload)


async def test_pricing_the_same_change_in_two_cities_gives_two_answers():
    server = build_server()
    args = dict(
        posted_at="2026-07-13T00:00:00+00:00",
        changed_at="2026-07-26T21:00:00+00:00",
        schedule_starts_at="2026-07-27T00:00:00+00:00",
        change_kind="add_shift", hourly_rate_dollars="18.00",
        hours_lost=0.0, hours_worked=8.0, hours_before_this_week=20.0,
    )
    nyc = await server.call_tool("price_schedule_change", {**args, "jurisdiction": "us-ny-nyc-fastfood"})
    chi = await server.call_tool("price_schedule_change", {**args, "jurisdiction": "us-il-chicago"})
    assert _payload(nyc) != _payload(chi)


async def test_pricing_cites_the_clause_it_used():
    server = build_server()
    result = await server.call_tool("price_schedule_change", {
        "jurisdiction": "us-ny-nyc-fastfood",
        "posted_at": "2026-07-13T00:00:00+00:00",
        "changed_at": "2026-07-26T21:00:00+00:00",
        "schedule_starts_at": "2026-07-27T00:00:00+00:00",
        "change_kind": "add_shift", "hourly_rate_dollars": "18.00",
        "hours_lost": 0.0, "hours_worked": 8.0, "hours_before_this_week": 20.0,
    })
    text = str(_payload(result))
    assert "DCWP" in text or "citation" in text


async def test_check_rest_reports_the_gap_the_remedy_and_whether_consent_is_needed():
    server = build_server()
    result = await server.call_tool("check_rest", {
        "jurisdiction": "us-il-chicago",
        "previous_shift_end": "2026-07-27T23:00:00+00:00",
        "next_shift_start": "2026-07-28T06:00:00+00:00",
        "hourly_rate_dollars": "18.00", "hours_worked": 8.0, "overtime_hours": 0.0,
    })
    text = str(_payload(result))
    assert "7.0" in text
    assert "no exceptions" in text.lower() or "consent" in text.lower()


async def test_an_unknown_jurisdiction_is_an_error_not_a_free_answer():
    server = build_server()
    with pytest.raises(Exception):
        await server.call_tool("price_schedule_change", {
            "jurisdiction": "us-tx-austin",
            "posted_at": "2026-07-13T00:00:00+00:00",
            "changed_at": "2026-07-26T21:00:00+00:00",
            "schedule_starts_at": "2026-07-27T00:00:00+00:00",
            "change_kind": "add_shift", "hourly_rate_dollars": "18.00",
            "hours_lost": 0.0, "hours_worked": 8.0, "hours_before_this_week": 20.0,
        })
