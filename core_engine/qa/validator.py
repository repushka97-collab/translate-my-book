from typing import List, Dict
import difflib
from core_engine.core.models import BookDocument, BlockType


def check_semantic_distance(src: str, dst: str) -> float:
    """
    Упрощённо: sequence matcher как заглушка до внедрения эмбеддингов.
    Возвращает 0..1 (1 — max similarity).
    """
    return difflib.SequenceMatcher(None, src, dst).ratio()


def ensure_integrity(doc: BookDocument) -> List[str]:
    issues: List[str] = []
    for page in doc.pages:
        for block in page.blocks:
            if block.normalized_text and not block.translated_text:
                issues.append(f"Block {block.id} not translated")
    return issues


def glossary_consistency(
    doc: BookDocument, glossary: Dict[str, str]
) -> List[str]:
    """
    Проверка, что термины переводятся единообразно.
    """
    issues: List[str] = []
    for term, expected in glossary.items():
        for page in doc.pages:
            for block in page.blocks:
                if not block.translated_text:
                    continue
                if term in (block.normalized_text or "") and expected not in block.translated_text:
                    issues.append(
                        f"Glossary mismatch: '{term}' in {block.id}, expected '{expected}'"
                    )
    return issues


def structure_compare(src_doc: BookDocument, dst_doc: BookDocument) -> List[str]:
    issues: List[str] = []
    if len(src_doc.pages) != len(dst_doc.pages):
        issues.append("Page count mismatch")
    # можно добавить более глубокую проверку
    return issues


def panel_letter_check(doc: BookDocument) -> List[str]:
    """
    Проверка панелей A/B/C в подрисунках (FIG. 1A, 1B...)
    """
    issues: List[str] = []
    # Заглушка, можно позже добавить анализ alt_text и captions
    return issues


def formula_check(doc: BookDocument) -> List[str]:
    issues: List[str] = []
    for page in doc.pages:
        for block in page.blocks:
            if block.type == BlockType.FORMULA:
                if "=" not in (block.translated_text or ""):
                    issues.append(f"Formula suspicious in block {block.id}")
    return issues


def reading_order_check(doc: BookDocument) -> List[str]:
    # Предполагаем, что порядок уже нормализован, просто place-holder
    return []


def run_all_checks(doc: BookDocument) -> Dict[str, List[str]]:
    return {
        "integrity": ensure_integrity(doc),
        "panel_letters": panel_letter_check(doc),
        "formula": formula_check(doc),
        "reading_order": reading_order_check(doc),
        # glossary и structure — снаружи (нужен src_doc и словарь)
    }

