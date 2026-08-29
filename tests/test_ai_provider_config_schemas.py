import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.security import EncryptionError, decrypt, encrypt
from app.schemas.ai_provider_config import (
    AiProviderConfigCreate,
    AiProviderConfigRead,
    AiProviderConfigUpdate,
)


def test_read_schema_cannot_carry_the_key():
    # The guarantee in CLAUDE.md section 7 is structural: there is no field for a
    # secret to leak through, so no route can accidentally return one.
    assert "api_key" not in AiProviderConfigRead.model_fields
    assert "api_key_preview" in AiProviderConfigRead.model_fields


def test_unknown_provider_is_rejected():
    with pytest.raises(ValidationError):
        AiProviderConfigCreate(provider="acme", model="m", api_key="k")


def test_create_defaults_to_inactive():
    config = AiProviderConfigCreate(provider="anthropic", model="claude-opus-5", api_key="k")

    assert config.is_active is False


def test_empty_api_key_is_rejected():
    with pytest.raises(ValidationError):
        AiProviderConfigCreate(provider="anthropic", model="claude-opus-5", api_key="")


def test_update_distinguishes_omitted_from_explicit():
    assert AiProviderConfigUpdate(is_active=True).model_dump(exclude_unset=True) == {
        "is_active": True
    }
    assert AiProviderConfigUpdate().model_dump(exclude_unset=True) == {}


def test_api_key_round_trips_through_encryption():
    key = Fernet.generate_key()

    assert decrypt(encrypt("sk-secret-value", key), key) == "sk-secret-value"


def test_ciphertext_does_not_contain_the_plaintext():
    assert "sk-secret-value" not in encrypt("sk-secret-value", Fernet.generate_key())


def test_decrypting_with_a_rotated_key_is_a_legible_error():
    ciphertext = encrypt("sk-secret-value", Fernet.generate_key())

    with pytest.raises(EncryptionError, match="AI_CONFIG_ENCRYPTION_KEY"):
        decrypt(ciphertext, Fernet.generate_key())
