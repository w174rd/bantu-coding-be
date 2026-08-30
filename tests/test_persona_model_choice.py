import pytest

from app.models.ai_provider_config import AiProviderConfig
from app.schemas.persona import PersonaUpdate
from app.services.ai import provider as provider_module
from app.services.ai.base import AIProviderError


class _Scalars:
    def __init__(self, value):
        self._value = value

    def one_or_none(self):
        return self._value


class FakeSession:
    """Just enough Session for get_provider: a row lookup and the active-config query."""

    def __init__(self, *, configs=None, active=None):
        self.configs = configs or {}
        self.active = active

    def get(self, model, primary_key):
        assert model is AiProviderConfig
        return self.configs.get(primary_key)

    def scalars(self, _statement):
        return _Scalars(self.active)


class FakePersona:
    def __init__(self, name, role_value, ai_provider_config_id=None):
        self.name = name
        self.role = type("Role", (), {"value": role_value})()
        self.ai_provider_config_id = ai_provider_config_id


def config(id_, provider="anthropic", model="claude-sonnet-4-5"):
    row = AiProviderConfig(
        id=id_, provider=provider, model=model, api_key="encrypted", is_active=False
    )
    row.id = id_
    return row


@pytest.fixture(autouse=True)
def _no_real_crypto(monkeypatch):
    # The choice of config is what these tests are about; decryption is not, and it
    # would otherwise need real key material from .env.
    monkeypatch.setattr(provider_module, "decrypt", lambda value, key: "plaintext-key")
    monkeypatch.setattr(provider_module, "get_ai_config_key", lambda: b"unused")


def test_a_persona_without_a_choice_falls_back_to_the_active_config():
    db = FakeSession(active=config(9, model="the-active-one"))
    persona = FakePersona("Architect", "architect")

    assert provider_module.get_provider(db, persona).model == "the-active-one"


def test_a_persona_with_a_choice_uses_it_over_the_active_config():
    db = FakeSession(
        configs={4: config(4, model="the-chosen-one")},
        active=config(9, model="the-active-one"),
    )
    persona = FakePersona("Challenger", "challenger", ai_provider_config_id=4)

    assert provider_module.get_provider(db, persona).model == "the-chosen-one"


def test_two_personas_can_resolve_to_different_models():
    db = FakeSession(
        configs={1: config(1, model="model-a"), 2: config(2, provider="groq", model="model-b")},
        active=config(9, model="the-active-one"),
    )

    first = provider_module.get_provider(db, FakePersona("Architect", "architect", 1))
    second = provider_module.get_provider(db, FakePersona("Researcher", "researcher", 2))

    assert (first.model, second.model) == ("model-a", "model-b")


def test_no_persona_at_all_still_uses_the_active_config():
    db = FakeSession(active=config(9, model="the-active-one"))

    assert provider_module.get_provider(db).model == "the-active-one"


def test_a_dangling_choice_names_the_persona():
    # ON DELETE SET NULL should make this unreachable. If it ever is reached, the
    # message has to say which of the four is misconfigured.
    db = FakeSession(configs={}, active=config(9))
    persona = FakePersona("Challenger", "challenger", ai_provider_config_id=404)

    with pytest.raises(AIProviderError) as caught:
        provider_module.get_provider(db, persona)

    assert "Challenger" in str(caught.value)
    assert caught.value.safe_to_display


def test_no_active_config_and_no_choice_is_still_the_old_error():
    db = FakeSession(active=None)

    with pytest.raises(AIProviderError, match="No active AI provider is configured"):
        provider_module.get_provider(db, FakePersona("Architect", "architect"))


def test_update_schema_tells_absent_apart_from_explicit_null():
    # PATCH semantics: omitting the field leaves the choice alone, sending null
    # clears it. Collapsing the two would make "follow the active model" unsendable.
    assert PersonaUpdate().model_dump(exclude_unset=True) == {}
    assert PersonaUpdate(ai_provider_config_id=None).model_dump(exclude_unset=True) == {
        "ai_provider_config_id": None
    }
    assert PersonaUpdate(ai_provider_config_id=7).model_dump(exclude_unset=True) == {
        "ai_provider_config_id": 7
    }
