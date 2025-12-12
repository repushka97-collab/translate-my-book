from __future__ import annotations

from typing import List, Dict, Any
import torch
import re
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

_MODEL_CACHE: Dict[str, Any] = {}
_TOKENIZER_CACHE: Dict[str, Any] = {}


def _load_nllb_model(model_name: str, device: str = "cuda"):
    """
    Р—Р°РіСЂСѓР¶Р°РµРј NLLB СЃ РєСЌС€РµРј Рё РїРѕРґРґРµСЂР¶РєРѕР№ CUDA/CPU.
    """
    if model_name in _MODEL_CACHE:
        return _TOKENIZER_CACHE[model_name], _MODEL_CACHE[model_name]

    print(f"[NLLB][LOAD] Loading model: {model_name} on device={device} ...")

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    if device == "cuda" and torch.cuda.is_available():
        # Speed knobs (safe defaults). TF32 can significantly speed up matmul on modern NVIDIA GPUs.
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:
            pass
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
        except Exception:
            pass

        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
        )
    else:
        print("[NLLB][WARN] CUDA not available -> using CPU")
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    try:
        model.eval()
    except Exception:
        pass

    _MODEL_CACHE[model_name] = model
    _TOKENIZER_CACHE[model_name] = tokenizer
    return tokenizer, model


def _sanitize_output(text: str, src_text: str) -> str:
    if not text:
        return src_text

    cleaned = re.sub(r"[\u0600-\u06FF]+", "", text)
    cleaned = cleaned.replace("В©", "").strip()

    if len(cleaned) < 3:
        return src_text

    return cleaned


def _split_into_chunks(text: str, max_chars: int = 350) -> List[str]:
    s = text.strip()
    if len(s) <= max_chars:
        return [s]

    sentences = re.split(r'(?<=[.!?вЂ¦])\s+', s)
    chunks: List[str] = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if len(sent) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(sent), max_chars):
                chunks.append(sent[i:i + max_chars].strip())
            continue

        if not current:
            current = sent
        elif len(current) + len(sent) + 1 <= max_chars:
            current = current + " " + sent
        else:
            chunks.append(current.strip())
            current = sent

    if current:
        chunks.append(current.strip())

    return chunks


def _resolve_lang_token(target_lang: str) -> str:
    """
    РњР°РїРїРёРЅРі "ru"/"en" в†’ СЃРїРµС†-С‚РѕРєРµРЅС‹ NLLB.
    """
    tl = (target_lang or "").lower()
    if tl.startswith("ru"):
        return "rus_Cyrl"
    if tl.startswith("en"):
        return "eng_Latn"
    # РґРµС„РѕР»С‚ вЂ” СЂСѓСЃСЃРєРёР№, С‡С‚РѕР±С‹ РЅРµ РїСЂРёР»РµС‚Р°Р» СЂР°РЅРґРѕРјРЅС‹Р№ СЏР·С‹Рє
    return "rus_Cyrl"


def translate_with_nllb(
    blocks: List[Dict[str, Any]],
    source_lang: str = "en",
    target_lang: str = "ru",
    batch_size: int = 8,
    max_length: int = 512,
    model_name: str = "facebook/nllb-200-distilled-1.3B",
    device: str = "cuda",
) -> List[Dict[str, Any]]:
    """
    РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ РїРµСЂРµРІРѕРґС‡РёРє NLLB (600M / 1.3B, CUDA/CPU, Р±Р°С‚С‡Рё).
    """
    tokenizer, model = _load_nllb_model(model_name, device=device)

    lang_token = _resolve_lang_token(target_lang)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(lang_token)

    translated_blocks: List[Dict[str, Any]] = []

    for i in range(0, len(blocks), batch_size):
        batch = blocks[i : i + batch_size]

        expanded_chunks: List[str] = []
        chunk_map: List[tuple[int, int]] = []

        for bi, b in enumerate(batch):
            src = b.get("text") or b.get("normalized_text") or ""
            if not src.strip():
                expanded_chunks.append("")
                chunk_map.append((bi, 0))
                continue

            parts = _split_into_chunks(src, max_chars=350)
            for pi, chunk in enumerate(parts):
                expanded_chunks.append(chunk)
                chunk_map.append((bi, pi))

        if not any(expanded_chunks):
            for b in batch:
                translated_blocks.append({**b, "translated_text": ""})
            continue

        inputs = tokenizer(
            expanded_chunks,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_length=max_length,
                num_beams=4,
            )

        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)

        # СЃРєР»РµРёРІР°РµРј С‡Р°РЅРєРё РѕР±СЂР°С‚РЅРѕ РїРѕ Р±Р»РѕРєР°Рј
        combo: Dict[int, List[str]] = {}
        for (bi, _), out in zip(chunk_map, decoded):
            combo.setdefault(bi, []).append(out)

        for local_i, b in enumerate(batch):
            parts = combo.get(local_i, [])
            cleaned_parts = [_sanitize_output(x, "") for x in parts]
            merged = " ".join(x.strip() for x in cleaned_parts if x.strip())
            if not merged:
                merged = b.get("text") or ""
            translated_blocks.append({**b, "translated_text": merged})

    return translated_blocks


