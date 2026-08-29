from app.core.config import Settings

# Deliberately generic. Tests must not encode the real role or database name —
# they are committed, and those identifiers stay out of the repo.


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "db_host": "127.0.0.1",
        "db_port": 5433,
        "db_user": "testuser",
        "db_password": "testpass",
        "db_name": "testdb",
        "ai_config_encryption_key": "dGVzdC1rZXktbm90LWEtcmVhbC1mZXJuZXQta2V5EQ=",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_database_url_is_assembled_from_parts():
    assert _settings().database_url == (
        "postgresql+psycopg://testuser:testpass@127.0.0.1:5433/testdb"
    )


def test_password_special_characters_are_encoded():
    url = _settings(db_password="p@ss/word").database_url

    assert "p%40ss%2Fword" in url
    assert url.endswith("@127.0.0.1:5433/testdb")


def test_cors_origins_split_on_commas():
    settings = _settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173")

    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
