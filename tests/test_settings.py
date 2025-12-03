import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.settings import Provider, ProviderCredential, ModelConfig, GlobalSetting
from services.settings import SettingsService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    # Create tables
    from models.settings import Provider, ProviderCredential, ModelConfig, GlobalSetting

    Provider.metadata.create_all(bind=engine)
    ProviderCredential.metadata.create_all(bind=engine)
    ModelConfig.metadata.create_all(bind=engine)
    GlobalSetting.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_get_settings_empty(db_session):
    service = SettingsService(db_session)
    result = service.get_all_settings()
    assert "providers" in result
    assert "global" in result
    assert result["providers"] == {}
    assert result["global"] == {}


def test_update_provider(db_session):
    service = SettingsService(db_session)
    provider = service.update_provider(
        "openai", {"display_name": "OpenAI", "capabilities": ["chat", "embedding"]}
    )

    assert provider.name == "openai"
    assert provider.display_name == "OpenAI"
    assert provider.capabilities == ["chat", "embedding"]

    # Test get settings includes the provider
    result = service.get_all_settings()
    assert "openai" in result["providers"]
    assert result["providers"]["openai"]["display_name"] == "OpenAI"
