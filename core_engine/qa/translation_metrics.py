# core_engine/qa/translation_metrics.py

from __future__ import annotations

from typing import List, Dict, Any, Optional
import re
from collections import Counter


def calculate_bleu_score(reference: str, candidate: str, n: int = 4) -> float:
    """
    Упрощенный расчет BLEU score (без нормализации и smoothing).
    Для точного расчета лучше использовать библиотеку sacrebleu.
    """
    def get_ngrams(text: str, n: int) -> Counter:
        words = text.split()
        ngrams = []
        for i in range(len(words) - n + 1):
            ngrams.append(tuple(words[i:i+n]))
        return Counter(ngrams)
    
    ref_ngrams = get_ngrams(reference.lower(), n)
    cand_ngrams = get_ngrams(candidate.lower(), n)
    
    if not ref_ngrams or not cand_ngrams:
        return 0.0
    
    matches = sum((ref_ngrams & cand_ngrams).values())
    total = sum(cand_ngrams.values())
    
    if total == 0:
        return 0.0
    
    precision = matches / total
    
    # Brevity penalty
    ref_len = len(reference.split())
    cand_len = len(candidate.split())
    if cand_len > ref_len:
        bp = 1.0
    else:
        bp = (cand_len / ref_len) if ref_len > 0 else 0.0
    
    return precision * bp


def calculate_rouge_l(reference: str, candidate: str) -> float:
    """
    Упрощенный расчет ROUGE-L (Longest Common Subsequence).
    """
    def lcs_length(s1: str, s2: str) -> int:
        words1 = s1.split()
        words2 = s2.split()
        m, n = len(words1), len(words2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if words1[i-1] == words2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
    
    ref_words = reference.split()
    cand_words = candidate.split()
    
    if not ref_words or not cand_words:
        return 0.0
    
    lcs = lcs_length(reference, candidate)
    precision = lcs / len(cand_words) if cand_words else 0.0
    recall = lcs / len(ref_words) if ref_words else 0.0
    
    if precision + recall == 0:
        return 0.0
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def calculate_length_ratio(source: str, target: str) -> float:
    """
    Соотношение длин исходного и переведенного текста.
    """
    src_len = len(source.split())
    tgt_len = len(target.split())
    
    if src_len == 0:
        return 0.0
    
    return tgt_len / src_len


def analyze_translation_quality(
    source_blocks: List[Dict[str, Any]],
    translated_blocks: List[Dict[str, Any]],
    reference_blocks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Анализирует качество перевода блоков.
    
    Возвращает метрики:
    - average_length_ratio: среднее соотношение длин
    - potential_issues: список потенциальных проблем
    - quality_score: общая оценка качества (0-1)
    """
    if len(source_blocks) != len(translated_blocks):
        return {
            "error": "Block count mismatch",
            "source_count": len(source_blocks),
            "translated_count": len(translated_blocks)
        }
    
    length_ratios = []
    quality_scores = []
    issues = []
    
    for i, (src_block, tgt_block) in enumerate(zip(source_blocks, translated_blocks)):
        src_text = (src_block.get("text") or src_block.get("normalized_text") or "").strip()
        tgt_text = (tgt_block.get("translated_text") or "").strip()
        
        if not src_text or not tgt_text:
            continue
        
        # Length ratio
        ratio = calculate_length_ratio(src_text, tgt_text)
        length_ratios.append(ratio)
        
        # Потенциальные проблемы
        if ratio < 0.3:
            issues.append({
                "block_id": src_block.get("id", f"block_{i}"),
                "type": "too_short",
                "message": f"Translation is too short (ratio: {ratio:.2f})",
                "severity": "medium"
            })
        elif ratio > 3.0:
            issues.append({
                "block_id": src_block.get("id", f"block_{i}"),
                "type": "too_long",
                "message": f"Translation is too long (ratio: {ratio:.2f})",
                "severity": "medium"
            })
        
        # Если есть референс - считаем BLEU/ROUGE
        if reference_blocks and i < len(reference_blocks):
            ref_text = (reference_blocks[i].get("text") or "").strip()
            if ref_text:
                bleu = calculate_bleu_score(ref_text, tgt_text)
                rouge = calculate_rouge_l(ref_text, tgt_text)
                quality_scores.append((bleu + rouge) / 2)
    
    avg_ratio = sum(length_ratios) / len(length_ratios) if length_ratios else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
    
    return {
        "average_length_ratio": avg_ratio,
        "quality_score": avg_quality,
        "potential_issues": issues,
        "total_blocks": len(source_blocks),
        "analyzed_blocks": len(length_ratios)
    }


def detect_translation_artifacts(text: str) -> List[Dict[str, Any]]:
    """
    Детектирует артефакты перевода:
    - Смешанные алфавиты
    - Повторяющиеся токены
    - Неправильная пунктуация
    """
    artifacts = []
    
    # Смешанные алфавиты (латиница в русском тексте)
    latin_words = re.findall(r'\b[a-zA-Z]+\b', text)
    if len(latin_words) > len(text.split()) * 0.1:  # Больше 10% латинских слов
        artifacts.append({
            "type": "mixed_alphabet",
            "severity": "medium",
            "message": f"Too many Latin words in Russian text: {len(latin_words)}"
        })
    
    # Повторяющиеся токены
    words = text.split()
    if len(words) > 2:
        for i in range(len(words) - 1):
            if words[i] == words[i+1] and len(words[i]) > 2:
                artifacts.append({
                    "type": "repeated_token",
                    "severity": "low",
                    "message": f"Repeated token: '{words[i]}'"
                })
                break  # Один артефакт на блок
    
    # Неправильная пунктуация (множественные пробелы перед знаками)
    if re.search(r'\s{2,}[,.!?;:]', text):
        artifacts.append({
            "type": "punctuation_spacing",
            "severity": "low",
            "message": "Multiple spaces before punctuation"
        })
    
    return artifacts

