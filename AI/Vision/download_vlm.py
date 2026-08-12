"""
CYNEXIS — Local Offline VLM Model Downloader
Downloads vikhyatk/moondream2 (Revision 2024-08-26) to local disk for 100% offline vision inference.
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from core.logger import setup_logging, get_logger
from core.config import settings

log = get_logger("download_vlm")

MODEL_ID = "vikhyatk/moondream2"
REVISION = "2024-08-26"
LOCAL_DIR = settings.resolve_path(settings.vision_model_path)


def download_and_save_model():
    setup_logging()
    log.info(f"Target local VLM directory: {LOCAL_DIR}")
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    weight_files = list(LOCAL_DIR.glob("*.safetensors")) + list(LOCAL_DIR.glob("*.bin"))
    if weight_files:
        log.info(f"Found existing local weights in {LOCAL_DIR} ({len(weight_files)} files). Model is already downloaded.")
        return True

    log.info(f"Downloading {MODEL_ID} (revision: {REVISION})...")
    t0 = time.time()

    # 1. Download and save Tokenizer
    log.info("Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID,
        revision=REVISION,
        trust_remote_code=True,
    )
    tokenizer.save_pretrained(str(LOCAL_DIR))
    log.info(f"Tokenizer saved to {LOCAL_DIR}")

    # 2. Download and save Model
    log.info("Downloading model weights (approx. 1.86 GB)...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=REVISION,
        trust_remote_code=True,
        torch_dtype=torch.float32,
    )
    model.save_pretrained(str(LOCAL_DIR))
    elapsed = time.time() - t0

    log.info(f"Moondream2 model successfully saved to {LOCAL_DIR} in {elapsed:.2f}s.")
    return True


if __name__ == "__main__":
    success = download_and_save_model()
    if not success:
        sys.exit(1)
