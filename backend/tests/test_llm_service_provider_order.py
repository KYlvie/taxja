from app.services.llm_service import LLMService


def _build_service() -> LLMService:
    service = LLMService.__new__(LLMService)
    service.groq_client = object()
    service.client = object()
    service.anthropic_client = object()
    service.gpt_oss_client = object()
    service.groq_model = "groq-text"
    service.groq_vision_model = "groq-vision"
    service.model = "openai-text"
    service.anthropic_model = "anthropic-text"
    service.anthropic_vision_model = "anthropic-vision"
    service.gpt_oss_model = "gpt-oss-text"
    return service


def test_text_provider_chain_defaults_to_groq_first():
    service = _build_service()

    providers = service._build_text_provider_chain()

    assert [name for name, _, _ in providers] == [
        "Groq",
        "OpenAI",
        "Anthropic",
        "GPT-OSS",
    ]


def test_vision_provider_chain_defaults_to_groq_first():
    service = _build_service()

    providers = service._build_vision_provider_chain()

    assert [provider["name"] for provider in providers] == [
        "groq",
        "openai",
        "anthropic",
        "gpt-oss",
    ]


def test_active_client_prefers_groq_for_text_and_vision():
    service = _build_service()

    text_client, text_model = service._get_active_client_and_model()
    vision_client, vision_model = service._get_active_client_and_model(
        prefer_vision=True
    )

    assert text_client is service.groq_client
    assert text_model == "groq-text"
    assert vision_client is service.groq_client
    assert vision_model == "groq-vision"
