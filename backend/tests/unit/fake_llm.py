import json
import re
from typing import Any

from app.services.llm_service import LlmRequest, LlmResponse


class FakeStructuredLlmClient:
    provider = "openai"
    model_name = "fake-openai-test-model"

    def generate(self, request: LlmRequest) -> LlmResponse:
        content = self._structured_content(request)
        return LlmResponse(
            content=content,
            response_payload={"content": content, "provider": self.provider, "model_name": self.model_name},
            prompt_tokens=len(request.prompt.split()),
            completion_tokens=max(1, len(content.split())),
        )

    def _structured_content(self, request: LlmRequest) -> str:
        if request.purpose == "input_guardrail":
            source_text = self._source_text(request.prompt)
            lowered = source_text.lower()
            blocked = any(
                marker in lowered
                for marker in [
                    "ignore previous",
                    "ignore all previous",
                    "system prompt",
                    "developer message",
                    "reveal your instructions",
                    "jailbreak",
                ]
            )
            return json.dumps(
                {
                    "allowed": not blocked,
                    "risk_level": "high" if blocked else "low",
                    "reason": "Prompt injection detected." if blocked else "Normal requirement input.",
                }
            )
        if request.purpose == "requirement_sufficiency":
            source_text = self._source_text(request.prompt)
            words = source_text.split()
            is_sufficient = len(words) >= 12 and any(
                word.lower().startswith(("user", "member", "admin", "patient")) for word in words
            )
            return json.dumps(
                {
                    "is_sufficient": is_sufficient,
                    "rationale": "Fake test sufficiency decision.",
                    "questions": []
                    if is_sufficient
                    else [
                        {
                            "id": "scope",
                            "question": "What are the main workflows and user roles?",
                            "reason": "The input is too vague for a useful SRS.",
                        }
                    ],
                }
            )
        if request.purpose == "summary":
            return json.dumps(
                {
                    "introduction": "Summary generated from the supplied stakeholder requirement text.",
                    "stakeholders": ["Users identified from the supplied requirement text"],
                    "use_cases": ["UC-001: Use the system capabilities described in the supplied requirement text"],
                    "glossary": [],
                }
            )
        if request.purpose == "requirement_extraction":
            source_text = self._source_text(request.prompt)
            sentences = self._sentences(source_text)
            return json.dumps(
                {
                    "requirements": [
                        {
                            "requirement_code": f"REQ-{index:03d}",
                            "requirement_text": self._shall_statement(sentence),
                            "source_trace": sentence,
                            "extraction_reason": "The source text describes an expected system capability or constraint.",
                            "confidence_score": 0.75,
                        }
                        for index, sentence in enumerate(sentences, start=1)
                    ]
                }
            )
        if request.purpose == "requirement_classification":
            requirements = self._requirements_from_prompt(request.prompt)
            return json.dumps({"requirements": [self._classify(item) for item in requirements]})
        return json.dumps({"content": request.prompt})

    @staticmethod
    def _source_text(prompt: str) -> str:
        if "UNTRUSTED_STAKEHOLDER_TEXT_START" in prompt:
            return prompt.rsplit("UNTRUSTED_STAKEHOLDER_TEXT_START", 1)[-1].split(
                "UNTRUSTED_STAKEHOLDER_TEXT_END", 1
            )[0].strip()
        if "Stakeholder input:" in prompt:
            return prompt.rsplit("Stakeholder input:", 1)[-1].strip()
        if "Source text:" in prompt:
            return prompt.rsplit("Source text:", 1)[-1].strip()
        return prompt.strip()

    @staticmethod
    def _sentences(text: str) -> list[str]:
        parts = [part.strip(" -\t") for part in re.split(r"[\n.;]+", text) if part.strip(" -\t")]
        return parts or ["The submitted requirement text"]

    @staticmethod
    def _shall_statement(sentence: str) -> str:
        cleaned = sentence.rstrip(".")
        if cleaned.lower().startswith("the system shall"):
            return cleaned
        return f"The system shall support {cleaned[0].lower()}{cleaned[1:]}"

    @staticmethod
    def _requirements_from_prompt(prompt: str) -> list[dict[str, Any]]:
        raw_json = prompt.rsplit("Requirements JSON:", 1)[-1].strip()
        parsed = json.loads(raw_json)
        requirements = parsed.get("requirements", [])
        return requirements if isinstance(requirements, list) else []

    @staticmethod
    def _classify(item: dict[str, Any]) -> dict[str, Any]:
        text = str(item.get("requirement_text", ""))
        lower_text = text.lower()
        subtype = None
        if any(keyword in lower_text for keyword in ["security", "secure", "auth", "password", "permission"]):
            subtype = "Security"
        elif any(keyword in lower_text for keyword in ["performance", "respond", "within", "second", "fast"]):
            subtype = "Performance"
        requirement_type = "non_functional" if subtype else "functional"
        return {
            "requirement_code": item.get("requirement_code", "REQ-001"),
            "requirement_text": text,
            "source_trace": item.get("source_trace", text),
            "extraction_reason": item.get("extraction_reason", "The item was extracted from the source text."),
            "confidence_score": item.get("confidence_score", 0.75),
            "requirement_type": requirement_type,
            "nfr_subtype": subtype,
            "classification_rationale": "Classified from the requirement wording.",
        }