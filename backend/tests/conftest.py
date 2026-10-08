import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def console_email_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests off real mail providers, whatever the local .env selects."""
    monkeypatch.setattr(settings, "email_delivery_mode", "console")
