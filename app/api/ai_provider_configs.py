from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import EncryptionError, decrypt, encrypt, get_ai_config_key
from app.db.session import get_db
from app.models.ai_provider_config import AiProviderConfig
from app.schemas.ai_provider_config import (
    AiProviderConfigCreate,
    AiProviderConfigRead,
    AiProviderConfigUpdate,
)

router = APIRouter(prefix="/api/v1/ai-provider-configs", tags=["ai-provider-configs"])


def _preview(config: AiProviderConfig) -> str:
    try:
        plaintext = decrypt(config.api_key, get_ai_config_key())
    except EncryptionError:
        # Written under a since-rotated key. Saying so keeps this row listable, so
        # it can still be re-keyed or deleted through the API.
        return "(unreadable)"
    return f"...{plaintext[-4:]}" if len(plaintext) > 4 else "..."


def _to_read(config: AiProviderConfig) -> AiProviderConfigRead:
    return AiProviderConfigRead(
        id=config.id,
        title=config.title,
        provider=config.provider,
        model=config.model,
        api_key_preview=_preview(config),
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _get_or_404(config_id: int, db: Session) -> AiProviderConfig:
    config = db.get(AiProviderConfig, config_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI provider config not found"
        )
    return config


def _deactivate_all(db: Session) -> None:
    db.execute(update(AiProviderConfig).values(is_active=False))


@router.get("", response_model=list[AiProviderConfigRead])
def list_ai_provider_configs(db: Session = Depends(get_db)) -> list[AiProviderConfigRead]:
    configs = db.scalars(select(AiProviderConfig).order_by(AiProviderConfig.id))
    return [_to_read(config) for config in configs]


@router.post(
    "", response_model=AiProviderConfigRead, status_code=status.HTTP_201_CREATED
)
def create_ai_provider_config(
    payload: AiProviderConfigCreate, db: Session = Depends(get_db)
) -> AiProviderConfigRead:
    if payload.is_active:
        _deactivate_all(db)

    config = AiProviderConfig(
        title=payload.title,
        provider=payload.provider,
        model=payload.model,
        api_key=encrypt(payload.api_key, get_ai_config_key()),
        is_active=payload.is_active,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return _to_read(config)


@router.patch("/{config_id}", response_model=AiProviderConfigRead)
def update_ai_provider_config(
    config_id: int, payload: AiProviderConfigUpdate, db: Session = Depends(get_db)
) -> AiProviderConfigRead:
    config = _get_or_404(config_id, db)
    fields = payload.model_dump(exclude_unset=True)

    # Cleared before the row itself is touched: exactly one config may be active,
    # and get_provider() raises if it ever sees two.
    if fields.get("is_active") is True:
        _deactivate_all(db)

    if "api_key" in fields:
        fields["api_key"] = encrypt(fields["api_key"], get_ai_config_key())
    for field, value in fields.items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)
    return _to_read(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai_provider_config(config_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_or_404(config_id, db))
    db.commit()
