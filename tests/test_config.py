from app.core.config import Settings


def test_cors_origins_are_loaded_from_comma_separated_setting():
    settings = Settings(cors_origins="https://a.example, https://b.example")
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
