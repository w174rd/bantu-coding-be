import json

import pytest

from app.core.enums import TicketStatus
from app.services.ai.base import AIProviderError
from app.services.arbiter import parse_verdict

VALID = {
    "headline": "Go with the queue.",
    "options": [
        {"label": "Queue", "percentage": 70, "rationale": "absorbs bursts"},
        {"label": "Retry loop", "percentage": 30, "rationale": "simpler but drops work"},
    ],
    "ticket": {"title": "Add a job queue", "body": "## Context\nIt crashes under load."},
}


def test_clean_json_is_accepted():
    verdict = parse_verdict(json.dumps(VALID))

    assert verdict.headline == "Go with the queue."
    assert [option.label for option in verdict.options] == ["Queue", "Retry loop"]


def test_json_wrapped_in_prose_and_a_code_fence_is_extracted():
    raw = f"Here is my decision:\n\n```json\n{json.dumps(VALID)}\n```\n\nHope that helps."

    assert parse_verdict(raw).headline == "Go with the queue."


def test_reply_with_no_json_is_rejected():
    with pytest.raises(AIProviderError, match="did not return a JSON object"):
        parse_verdict("I think we should probably use a queue.")


def test_malformed_json_is_rejected():
    with pytest.raises(AIProviderError, match="could not be parsed"):
        parse_verdict('{"headline": "oops", "options": [,]}')


def test_missing_ticket_is_rejected():
    payload = {k: v for k, v in VALID.items() if k != "ticket"}

    with pytest.raises(AIProviderError, match="failed validation"):
        parse_verdict(json.dumps(payload))


def test_empty_options_is_rejected():
    with pytest.raises(AIProviderError, match="failed validation"):
        parse_verdict(json.dumps({**VALID, "options": []}))


def test_overlong_title_is_rejected():
    payload = {**VALID, "ticket": {"title": "x" * 201, "body": "b"}}

    with pytest.raises(AIProviderError, match="failed validation"):
        parse_verdict(json.dumps(payload))


def test_rounding_drift_is_normalised():
    payload = {
        **VALID,
        "options": [
            {"label": "Queue", "percentage": 67, "rationale": "r"},
            {"label": "Retry", "percentage": 30, "rationale": "r"},
        ],
    }

    verdict = parse_verdict(json.dumps(payload))

    assert sum(option.percentage for option in verdict.options) == pytest.approx(100)


def test_percentages_far_from_100_are_rejected():
    payload = {
        **VALID,
        "options": [
            {"label": "Queue", "percentage": 20, "rationale": "r"},
            {"label": "Retry", "percentage": 20, "rationale": "r"},
        ],
    }

    with pytest.raises(AIProviderError, match="sum to 40"):
        parse_verdict(json.dumps(payload))


def test_a_status_in_the_model_output_is_not_a_field_the_verdict_can_carry():
    # The drag gate in code: the Arbiter has no channel through which to place a
    # ticket anywhere but Backlog, because ArbiterTicket has no status field at all.
    payload = {**VALID, "ticket": {**VALID["ticket"], "status": "in_progress"}}

    verdict = parse_verdict(json.dumps(payload))

    assert not hasattr(verdict.ticket, "status")
    assert TicketStatus.BACKLOG.value == "backlog"
