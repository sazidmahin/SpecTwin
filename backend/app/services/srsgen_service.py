from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.llm_service import LlmConfigurationError, LlmRequest, LlmResponse


class SrsGenClient:
    provider = "srsgen"

    def __init__(
        self,
        *,
        artifact_path: str | Path | None = None,
        base_model: str | None = None,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
        model: Any | None = None,
        tokenizer: Any | None = None,
    ) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        configured_path = Path(artifact_path or settings.srsgen_artifact_path)
        self.artifact_path = configured_path if configured_path.is_absolute() else backend_root / configured_path
        self.model_name = base_model or settings.srsgen_base_model
        self.max_new_tokens = max_new_tokens or settings.srsgen_max_new_tokens
        self.temperature = settings.srsgen_temperature if temperature is None else temperature
        self._model = model
        self._tokenizer = tokenizer
        self._load_lock = threading.Lock()
        self._generate_lock = threading.Lock()

    def validate_configuration(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        required = [
            self.artifact_path / "base_model" / "config.json",
            self.artifact_path / "lora_adapter" / "adapter_config.json",
        ]
        missing = [path.relative_to(self.artifact_path).as_posix() for path in required if not path.is_file()]
        if missing:
            raise LlmConfigurationError(
                f"SrsGen artifact is not installed at {self.artifact_path}. Missing: {', '.join(missing)}"
            )

    def _load(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        with self._load_lock:
            if self._model is not None and self._tokenizer is not None:
                return
            self.validate_configuration()
            try:
                import torch
                from peft import PeftModel
                from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            except ImportError as exc:
                raise LlmConfigurationError(
                    "Install torch, transformers, accelerate, bitsandbytes, and peft in the SrsGen runtime environment"
                ) from exc
            if settings.srsgen_load_in_4bit and not torch.cuda.is_available():
                raise LlmConfigurationError("4-bit SrsGen inference requires a CUDA-capable GPU")
            base_model_path = self.artifact_path / "base_model"
            adapter_path = self.artifact_path / "lora_adapter"
            quantization = None
            if settings.srsgen_load_in_4bit:
                compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                quantization = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=compute_dtype,
                    bnb_4bit_use_double_quant=True,
                )
            tokenizer = AutoTokenizer.from_pretrained(base_model_path, use_fast=True, local_files_only=True)
            if tokenizer.pad_token_id is None:
                tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForCausalLM.from_pretrained(
                base_model_path,
                quantization_config=quantization,
                device_map="auto",
                torch_dtype="auto",
                local_files_only=True,
            )
            self._model = PeftModel.from_pretrained(model, adapter_path, local_files_only=True)
            self._model.eval()
            self._tokenizer = tokenizer
            self.model_name = "srsgen-qwen1.5-local+qlora"

    def generate(self, request: LlmRequest) -> LlmResponse:
        self._load()
        assert self._model is not None and self._tokenizer is not None
        messages = [
            {"role": "system", "content": "You are SrsGen. Follow the requested JSON contract exactly."},
            {"role": "user", "content": request.prompt},
        ]
        with self._generate_lock:
            inputs = self._tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self._model.device)
            generation_kwargs: dict[str, Any] = {
                "max_new_tokens": self.max_new_tokens,
                "do_sample": self.temperature > 0,
                "pad_token_id": self._tokenizer.pad_token_id,
                "eos_token_id": self._tokenizer.eos_token_id,
            }
            if self.temperature > 0:
                generation_kwargs["temperature"] = self.temperature
            outputs = self._model.generate(**inputs, **generation_kwargs)
            input_tokens = int(inputs["input_ids"].shape[-1])
            generated = outputs[0][input_tokens:]
            content = self._tokenizer.decode(generated, skip_special_tokens=True).strip()
        completion_tokens = int(generated.shape[-1])
        return LlmResponse(
            content=content,
            response_payload={
                "content": content,
                "provider": self.provider,
                "model_name": self.model_name,
                "artifact_path": str(self.artifact_path),
            },
            prompt_tokens=input_tokens,
            completion_tokens=completion_tokens,
        )
