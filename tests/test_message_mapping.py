from types import SimpleNamespace

from app.core.enums import MessageAuthorKind, PersonaRole
from app.services.discussion import build_provider_messages, window


def persona(id: int, role: PersonaRole, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=id, role=role, name=name)


ARCHITECT = persona(1, PersonaRole.ARCHITECT, "Architect")
CHALLENGER = persona(3, PersonaRole.CHALLENGER, "Challenger")
PERSONAS = {ARCHITECT.id: ARCHITECT, CHALLENGER.id: CHALLENGER}


def message(content: str, kind=MessageAuthorKind.USER, persona_id=None, source_name=None):
    return SimpleNamespace(
        content=content, author_kind=kind, persona_id=persona_id, source_name=source_name
    )


def test_own_messages_become_assistant_turns():
    history = [
        message("the app crashes"),
        message("use a queue", MessageAuthorKind.PERSONA, ARCHITECT.id),
    ]

    mapped = build_provider_messages(history, ARCHITECT, PERSONAS)

    assert [entry["role"] for entry in mapped] == ["user", "assistant"]
    assert mapped[1]["content"] == "use a queue"


def test_other_speakers_are_labelled():
    history = [
        message("the app crashes"),
        message("a queue will not help", MessageAuthorKind.PERSONA, CHALLENGER.id),
    ]

    mapped = build_provider_messages(history, ARCHITECT, PERSONAS)

    assert mapped[0]["role"] == "user"
    assert "You: the app crashes" in mapped[0]["content"]
    assert "Challenger: a queue will not help" in mapped[0]["content"]


def test_consecutive_user_turns_are_merged():
    history = [
        message("first"),
        message("second"),
        message("third", MessageAuthorKind.PERSONA, CHALLENGER.id),
    ]

    mapped = build_provider_messages(history, ARCHITECT, PERSONAS)

    assert len(mapped) == 1
    assert mapped[0]["content"].count("\n\n") == 2


def test_documents_are_labelled_with_their_filename():
    history = [message("stack trace", MessageAuthorKind.DOCUMENT, source_name="crash.md")]

    mapped = build_provider_messages(history, ARCHITECT, PERSONAS)

    assert mapped[0]["content"].startswith("Document (crash.md): ")


def test_leading_assistant_turn_is_dropped():
    # Providers reject a conversation that opens on an assistant turn, which happens
    # whenever the persona's own earlier line is the oldest message left after windowing.
    history = [message("mine", MessageAuthorKind.PERSONA, ARCHITECT.id), message("yours")]

    mapped = build_provider_messages(history, ARCHITECT, PERSONAS)

    assert [entry["role"] for entry in mapped] == ["user"]


def test_window_keeps_newest_within_budget():
    history = [message("a" * 100), message("b" * 100), message("c" * 100)]

    kept = window(history, budget=250)

    assert [entry.content[0] for entry in kept] == ["b", "c"]


def test_window_always_keeps_the_newest_message():
    history = [message("a" * 100), message("b" * 500)]

    kept = window(history, budget=10)

    assert len(kept) == 1
    assert kept[0].content[0] == "b"


def test_window_of_empty_history():
    assert window([], budget=100) == []
