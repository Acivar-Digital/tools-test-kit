"""
Unit tests for Day 10: Config Settings
Tests Pydantic Settings configuration and environment variable loading.
"""
import os
from unittest.mock import patch


class TestSettings:
    def test_settings_loads_defaults(self):
        from src.config.settings import Settings
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://test:test@localhost/testdb", "APP_PORT": "8443"}, clear=False):
            s = Settings()
            assert s.s3_endpoint == "http://localhost:9000"
            assert s.s3_bucket == "baziforecaster"
            assert s.app_port == "8443"

    def test_settings_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("S3_ENDPOINT", "http://custom:9000")
        monkeypatch.setenv("S3_BUCKET", "custom-bucket")
        monkeypatch.setenv("APP_PORT", "9000")
        from src.config.settings import Settings
        s = Settings()
        assert s.s3_endpoint == "http://custom:9000"
        assert s.s3_bucket == "custom-bucket"
        assert s.app_port == "9000"

    def test_settings_singleton_exists(self):
        from src.config.settings import settings
        assert settings is not None

    def test_settings_database_url_is_required(self):
        from src.config.settings import Settings
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://test:test@localhost/testdb"}):
            s = Settings()
            assert "postgresql" in str(s.database_url)
