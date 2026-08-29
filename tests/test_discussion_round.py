from types import SimpleNamespace

from app.core.enums import PersonaRole
from app.services.discussion import ROUND_ORDER, cadence


def test_round_order_is_architect_researcher_challenger():
    assert ROUND_ORDER == (
        PersonaRole.ARCHITECT,
        PersonaRole.RESEARCHER,
        PersonaRole.CHALLENGER,
    )


def test_the_arbiter_never_speaks_inside_a_round():
    # It runs after the round, on the cadence, not as a fourth turn every time.
    assert PersonaRole.ARBITER not in ROUND_ORDER


def test_cadence_falls_back_to_the_global_setting():
    assert cadence(SimpleNamespace(arbiter_every_n_rounds=None)) == 2


def test_a_conversation_can_override_the_cadence():
    assert cadence(SimpleNamespace(arbiter_every_n_rounds=3)) == 3


def test_verdict_fires_on_the_second_round_by_default():
    conversation = SimpleNamespace(arbiter_every_n_rounds=None)

    fires = [index for index in (1, 2, 3, 4) if index % cadence(conversation) == 0]

    assert fires == [2, 4]
