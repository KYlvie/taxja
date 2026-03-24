from app.services.llm_service import LLMService


def _make_service() -> LLMService:
    service = LLMService.__new__(LLMService)
    service.client = object()
    service.model = "gpt-4o"
    service.anthropic_client = object()
    service.anthropic_vision_model = "claude-opus-4-1-20250805"
    service.gpt_oss_client = object()
    service.gpt_oss_model = "openai/gpt-oss-120b"
    service.groq_client = object()
    service.groq_vision_model = "groq-vision"
    return service


def test_vision_provider_chain_defaults_to_openai_then_anthropic_before_groq():
    service = _make_service()

    chain = service._build_vision_provider_chain()

    assert [provider["name"] for provider in chain] == [
        "openai",
        "anthropic",
        "gpt-oss",
        "groq",
    ]


def test_vision_provider_chain_can_prefer_anthropic_for_manual_reruns():
    service = _make_service()

    chain = service._build_vision_provider_chain(prefer_provider="anthropic")

    assert [provider["name"] for provider in chain] == [
        "anthropic",
        "openai",
        "gpt-oss",
        "groq",
    ]
