import pytest

from app.services.llm_service import LlmConfigurationError, LlmRequest
from app.services.srsgen_service import SrsGenClient


class FakeInputs(dict):
    def to(self, device: str):
        return self


class FakeInputIds:
    shape = (1, 3)


class FakeGenerated:
    shape = (2,)


class FakeSequence:
    def __getitem__(self, key):
        return FakeGenerated()


class FakeTokenizer:
    pad_token_id = 0
    eos_token_id = 1

    def apply_chat_template(self, messages, **kwargs):
        assert messages[0]["role"] == "system"
        assert kwargs["add_generation_prompt"] is True
        return FakeInputs(input_ids=FakeInputIds())

    def decode(self, generated, *, skip_special_tokens: bool):
        assert skip_special_tokens is True
        return '{"requirements": []}'


class FakeModel:
    device = "cuda:0"

    def generate(self, **kwargs):
        assert kwargs["max_new_tokens"] == 64
        return [FakeSequence()]


def test_srsgen_reports_missing_uploaded_artifacts() -> None:
    client = SrsGenClient(artifact_path="definitely-missing-srsgen-artifact")
    with pytest.raises(LlmConfigurationError, match="base_model/config.json"):
        client.validate_configuration()


def test_srsgen_uses_injected_runtime_without_training_or_download() -> None:
    client = SrsGenClient(
        artifact_path="injected-test-runtime",
        model=FakeModel(),
        tokenizer=FakeTokenizer(),
        max_new_tokens=64,
    )
    response = client.generate(LlmRequest(prompt="Generate JSON", purpose="pipeline_requirements"))

    assert response.content == '{"requirements": []}'
    assert response.prompt_tokens == 3
    assert response.completion_tokens == 2
    assert response.response_payload["provider"] == "srsgen"
