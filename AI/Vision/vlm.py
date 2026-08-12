"""
CYNEXIS — Local Offline VLM Provider
Processes camera optical frames locally using Moondream2 to produce natural language scene descriptions with zero cloud dependencies.
"""

import io
import time
import asyncio
from pathlib import Path
from typing import Optional
from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from core.logger import get_logger
from core.config import settings
from AI.Vision.provider import VisionProvider

log = get_logger("vlm")


class LocalVLMProvider(VisionProvider):
    """
    Local offline Vision-Language Model provider.
    Runs locally on edge hardware with zero external cloud dependencies.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_name = getattr(settings, "vision_model_name", "vikhyatk/moondream2")
        self.model_revision = getattr(settings, "vision_model_revision", "2024-08-26")
        self.model_path = model_path or getattr(settings, "vision_model_path", "./AI Models/VLM/moondream2")
        self.device = getattr(settings, "vision_device", "cpu")
        self._loaded = False
        self._model = None
        self._tokenizer = None
        self._loading_lock = asyncio.Lock()
        log.info(f"LocalVLMProvider initialized (model={self.model_name}, device={self.device})")

    def is_loaded(self) -> bool:
        return self._loaded and (self._model is not None)

    async def load(self) -> bool:
        """Load tokenizer and model weights into memory."""
        if self.is_loaded():
            return True

        async with self._loading_lock:
            if self.is_loaded():
                return True

            try:
                resolved_path = settings.resolve_path(self.model_path)
                log.info(f"Loading local Vision Model from '{resolved_path}' on {self.device}...")
                t0 = time.time()

                def _load_sync():
                    # Determine torch_dtype from settings/env
                    import os
                    dtype_str = os.environ.get("VISION_DTYPE", getattr(settings, "vision_dtype", "float32")).lower()
                    if dtype_str == "bfloat16":
                        t_dtype = torch.bfloat16
                    elif dtype_str == "float16":
                        t_dtype = torch.float16
                    else:
                        t_dtype = torch.float32
                    log.info(f"Using model torch_dtype={t_dtype}")

                    # 1. Prefer offline local storage if weights exist
                    if resolved_path.exists() and any(resolved_path.glob("*.safetensors")):
                        log.info(f"Loading model strictly OFFLINE from {resolved_path}...")
                        tokenizer = AutoTokenizer.from_pretrained(
                            str(resolved_path),
                            local_files_only=True,
                            trust_remote_code=True,
                        )
                        model = AutoModelForCausalLM.from_pretrained(
                            str(resolved_path),
                            local_files_only=True,
                            trust_remote_code=True,
                            torch_dtype=t_dtype,
                        )
                    else:
                        # 2. Fallback to model name with cache
                        log.info(f"Loading model '{self.model_name}' (rev: {self.model_revision})...")
                        tokenizer = AutoTokenizer.from_pretrained(
                            self.model_name,
                            revision=self.model_revision,
                            trust_remote_code=True,
                        )
                        model = AutoModelForCausalLM.from_pretrained(
                            self.model_name,
                            revision=self.model_revision,
                            trust_remote_code=True,
                            torch_dtype=t_dtype,
                        )
                    model.eval()
                    return model, tokenizer

                self._model, self._tokenizer = await asyncio.to_thread(_load_sync)
                
                # Monkey-patch prepare_inputs_for_generation to handle local offline VLM cache synchronization
                original_prep = self._model.text_model.prepare_inputs_for_generation
                
                import functools
                @functools.wraps(original_prep)
                def patched_prep(
                    input_ids,
                    past_key_values=None,
                    attention_mask=None,
                    inputs_embeds=None,
                    cache_position=None,
                    position_ids=None,
                    use_cache=True,
                    num_logits_to_keep=0,
                    **kwargs,
                ):
                    has_cache = False
                    if past_key_values is not None:
                        try:
                            if hasattr(past_key_values, "get_seq_length") and past_key_values.get_seq_length() > 0:
                                has_cache = True
                            elif isinstance(past_key_values, tuple) and len(past_key_values) > 0 and len(past_key_values[0]) > 0:
                                has_cache = True
                        except Exception:
                            pass
                    
                    if has_cache:
                        inputs_embeds = None
                        # Slice input_ids to keep only the last generated token
                        input_ids = input_ids[:, -1:]
                        try:
                            past_length = past_key_values.get_seq_length() if hasattr(past_key_values, "get_seq_length") else past_key_values[0][0].shape[-2]
                        except Exception:
                            past_length = 0
                        # Override cache_position and position_ids to align with actual cache sequence length
                        cache_position = torch.tensor([past_length], device=input_ids.device)
                        position_ids = torch.tensor([[past_length]], device=input_ids.device)
                        if attention_mask is not None:
                            attention_mask = torch.ones((input_ids.shape[0], past_length + 1), dtype=torch.long, device=input_ids.device)
                    
                    model_inputs = original_prep(
                        input_ids,
                        past_key_values=past_key_values,
                        attention_mask=attention_mask,
                        inputs_embeds=inputs_embeds,
                        cache_position=cache_position,
                        position_ids=position_ids,
                        use_cache=use_cache,
                        num_logits_to_keep=num_logits_to_keep,
                        **kwargs,
                    )
                    
                    # Prefill step adjustments
                    if not has_cache:
                        if attention_mask is not None:
                            model_inputs["attention_mask"] = attention_mask
                        # Use correct prompt sequence length for prefill positions
                        seq_len = attention_mask.shape[1] if attention_mask is not None else (inputs_embeds.shape[1] if inputs_embeds is not None else 1)
                        model_inputs["cache_position"] = torch.arange(0, seq_len, device=input_ids.device)
                        model_inputs["position_ids"] = torch.arange(0, seq_len, device=input_ids.device).unsqueeze(0)
                            
                    return model_inputs
                
                self._model.text_model.prepare_inputs_for_generation = patched_prep
                
                self._loaded = True
                dt = time.time() - t0
                log.info(f"Local Vision Model loaded successfully in {dt:.3f}s")
                return True
            except Exception as e:
                log.error(f"Failed to load Vision Model: {e}")
                self._loaded = False
                return False

    async def unload(self) -> None:
        async with self._loading_lock:
            self._model = None
            self._tokenizer = None
            self._loaded = False
            log.info("Local Vision Model unloaded")

    async def describe_image(self, image_data: bytes, prompt: str = "Describe what you see.") -> str:
        """Processes raw JPEG bytes and produces natural language scene description."""
        if not image_data:
            return "No optical input provided."

        if not self.is_loaded():
            loaded = await self.load()
            if not loaded or self._model is None:
                return "Vision model is not loaded."

        try:
            def _analyze():
                img = Image.open(io.BytesIO(image_data)).convert("RGB")
                with torch.no_grad():
                    enc_image = self._model.encode_image(img)
                    answer = self._model.answer_question(
                        enc_image,
                        prompt,
                        self._tokenizer,
                        max_new_tokens=32,
                        do_sample=True,
                        temperature=0.5,
                        repetition_penalty=1.2,
                    )
                    return answer.strip()

            t0 = time.time()
            description = await asyncio.to_thread(_analyze)
            dt = time.time() - t0
            log.info(f"VLM inference completed in {dt:.3f}s: '{description}'")
            return description
        except Exception as e:
            import traceback
            traceback.print_exc()
            log.error(f"Vision analysis failed: {e}")
            return "I am unable to clearly distinguish the objects in view."
