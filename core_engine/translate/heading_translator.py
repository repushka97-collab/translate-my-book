# core_engine/translate/heading_translator.py

from __future__ import annotations

from typing import Dict, Any, List
import re


# Словарь частых заголовков для точного перевода
HEADING_DICTIONARY = {
    # Общие заголовки
    "INDEPENDENT LEARNING ACTIVITIES": "САМОСТОЯТЕЛЬНЫЕ УЧЕБНЫЕ ЗАДАНИЯ",
    "INDEPENDENT LEARNING": "САМОСТОЯТЕЛЬНОЕ ОБУЧЕНИЕ",
    "LEARNING ACTIVITIES": "УЧЕБНЫЕ ЗАДАНИЯ",
    "CHAPTER": "ГЛАВА",
    "PART": "ЧАСТЬ",
    "SECTION": "РАЗДЕЛ",
    "INTRODUCTION": "ВВЕДЕНИЕ",
    "CONCLUSION": "ЗАКЛЮЧЕНИЕ",
    "ABSTRACT": "АННОТАЦИЯ",
    "SUMMARY": "РЕЗЮМЕ",
    "REFERENCES": "ЛИТЕРАТУРА",
    "BIBLIOGRAPHY": "БИБЛИОГРАФИЯ",
    "INDEX": "УКАЗАТЕЛЬ",
    "TABLE OF CONTENTS": "СОДЕРЖАНИЕ",
    "APPENDIX": "ПРИЛОЖЕНИЕ",
    
    # Медицинские/научные
    "METHODS": "МЕТОДЫ",
    "RESULTS": "РЕЗУЛЬТАТЫ",
    "DISCUSSION": "ОБСУЖДЕНИЕ",
    "BACKGROUND": "ОБЗОР ЛИТЕРАТУРЫ",
    "OBJECTIVES": "ЦЕЛИ",
    "MATERIALS AND METHODS": "МАТЕРИАЛЫ И МЕТОДЫ",
    "CLINICAL CASE": "КЛИНИЧЕСКИЙ СЛУЧАЙ",
    "CASE STUDY": "КЛИНИЧЕСКИЙ СЛУЧАЙ",
    
    # Физиотерапия/медицина
    "EXERCISE SAFETY": "БЕЗОПАСНОСТЬ УПРАЖНЕНИЙ",
    "SAFETY": "БЕЗОПАСНОСТЬ",
    "TYPES OF THERAPEUTIC EXERCISE INTERVENTION": "ВИДЫ ТЕРАПЕВТИЧЕСКИХ УПРАЖНЕНИЙ",
    "THERAPEUTIC EXERCISE": "ТЕРАПЕВТИЧЕСКИЕ УПРАЖНЕНИЯ",
    "THERAPEUTIC EXERCISE INTERVENTIONS": "ТЕРАПЕВТИЧЕСКИЕ УПРАЖНЕНИЯ",
    "THERAPEUTIC EXERCISES": "ТЕРАПЕВТИЧЕСКИЕ УПРАЖНЕНИЯ",
    "FOUNDATIONAL CONCEPTS": "ОСНОВНЫЕ ПОНЯТИЯ",
    "GENERAL CONCEPTS": "ОБЩИЕ ПОНЯТИЯ",
    "DEFINITION": "ОПРЕДЕЛЕНИЕ",
    "DEFINITIONS": "ОПРЕДЕЛЕНИЯ",
    "PHYSICAL FUNCTION": "ФИЗИЧЕСКАЯ ФУНКЦИЯ",
    "IMPACT ON PHYSICAL FUNCTION": "ВЛИЯНИЕ НА ФИЗИЧЕСКУЮ ФУНКЦИЮ",
    "ASPECTS OF PHYSICAL FUNCTION": "АСПЕКТЫ ФИЗИЧЕСКОЙ ФУНКЦИИ",
    "KEY TERMS": "КЛЮЧЕВЫЕ ТЕРМИНЫ",
    "DEFINITION OF KEY TERMS": "ОПРЕДЕЛЕНИЕ КЛЮЧЕВЫХ ТЕРМИНОВ",
    "STRATEGIES FOR EFFECTIVE EXERCISE": "СТРАТЕГИИ ЭФФЕКТИВНЫХ УПРАЖНЕНИЙ",
    "TASK-SPECIFIC INSTRUCTION": "ИНСТРУКЦИИ ПО КОНКРЕТНЫМ ЗАДАЧАМ",
    "PREPARATION FOR EXERCISE INSTRUCTION": "ПОДГОТОВКА К ИНСТРУКЦИЯМ ПО УПРАЖНЕНИЯМ",
    "CONCEPTS OF MOTOR LEARNING": "КОНЦЕПЦИИ ДВИГАТЕЛЬНОГО ОБУЧЕНИЯ",
    "A FOUNDATION": "ОСНОВА",
    "FOUNDATION": "ОСНОВА",
    "EXERCISE COMPLIANCE": "СОБЛЮДЕНИЕ УПРАЖНЕНИЙ",
    "ADHERENCE TO EXERCISE": "СОБЛЮДЕНИЕ УПРАЖНЕНИЙ",
    "DISABILITY PROCESS": "ПРОЦЕСС ИНВАЛИДНОСТИ",
    "THE DISABLEMENT PROCESS": "ПРОЦЕСС ИНВАЛИДНОСТИ",
    "PROCESS AND MODELS OF DISABLEMENT": "ПРОЦЕСС И МОДЕЛИ ИНВАЛИДНОСТИ",
    "MODELS OF DISABILITY": "МОДЕЛИ ИНВАЛИДНОСТИ",
    "MODELS OF DISABLEMENT": "МОДЕЛИ ИНВАЛИДНОСТИ",
    "USING MODELS AND CLASSIFICATIONS": "ИСПОЛЬЗОВАНИЕ МОДЕЛЕЙ И КЛАССИФИКАЦИЙ",
    "USE OF DISABLEMENT MODELS AND CLASSIFICATIONS IN PHYSICAL THERAPY": "ИСПОЛЬЗОВАНИЕ МОДЕЛЕЙ ИНВАЛИДНОСТИ И КЛАССИФИКАЦИЙ В ФИЗИЧЕСКОЙ ТЕРАПИИ",
    "IN PHYSICAL THERAPY": "В ФИЗИЧЕСКОЙ ТЕРАПИИ",
    "PATIENT MANAGEMENT AND CLINICAL DECISION MAKING": "ВЕДЕНИЕ ПАЦИЕНТА И КЛИНИЧЕСКОЕ ПРИНЯТИЕ РЕШЕНИЙ",
    "PATIENT MANAGEMENT AND CLINICAL DECISION MAKING: AN INTERACTIVE RELATIONSHIP": "ВЕДЕНИЕ ПАЦИЕНТА И КЛИНИЧЕСКОЕ ПРИНЯТИЕ РЕШЕНИЙ: ИНТЕРАКТИВНЫЕ ОТНОШЕНИЯ",
    "CLINICAL DECISION MAKING": "КЛИНИЧЕСКОЕ ПРИНЯТИЕ РЕШЕНИЙ",
    "EVIDENCE-BASED PRACTICE": "ПРАКТИКА, ОСНОВАННАЯ НА ДОКАЗАТЕЛЬСТВАХ",
    "A PATIENT MANAGEMENT MODEL": "МОДЕЛЬ ВЕДЕНИЯ ПАЦИЕНТА",
    "PATIENT MANAGEMENT MODEL": "МОДЕЛЬ ВЕДЕНИЯ ПАЦИЕНТА",
    "STRATEGIES FOR EFFECTIVE EXERCISE AND TASK-SPECIFIC INSTRUCTION": "СТРАТЕГИИ ЭФФЕКТИВНЫХ УПРАЖНЕНИЙ И ИНСТРУКЦИЙ ПО КОНКРЕТНЫМ ЗАДАЧАМ",
    "PREPARATION FOR EXERCISE INSTRUCTION": "ПОДГОТОВКА К ИНСТРУКЦИЯМ ПО УПРАЖНЕНИЯМ",
    "CONCEPTS OF MOTOR LEARNING": "КОНЦЕПЦИИ ДВИГАТЕЛЬНОГО ОБУЧЕНИЯ",
    "CONCEPTS OF MOTOR LEARNING: A FOUNDATION OF EXERCISE AND TASK-SPECIFIC INSTRUCTION": "КОНЦЕПЦИИ ДВИГАТЕЛЬНОГО ОБУЧЕНИЯ: ОСНОВА УПРАЖНЕНИЙ И ИНСТРУКЦИЙ ПО КОНКРЕТНЫМ ЗАДАЧАМ",
    "DEFINITION OF THERAPEUTIC EXERCISE": "ОПРЕДЕЛЕНИЕ ТЕРАПЕВТИЧЕСКИХ УПРАЖНЕНИЙ",
    "ASPECTS OF PHYSICAL FUNCTION: DEFINITION OF KEY TERMS": "АСПЕКТЫ ФИЗИЧЕСКОЙ ФУНКЦИИ: ОПРЕДЕЛЕНИЕ КЛЮЧЕВЫХ ТЕРМИНОВ",
    
    # Анатомия/физиология
    "ANATOMY": "АНАТОМИЯ",
    "PHYSIOLOGY": "ФИЗИОЛОГИЯ",
    "PATHOLOGY": "ПАТОЛОГИЯ",
    "KINESIOLOGY": "КИНЕЗИОЛОГИЯ",
    
    # Упражнения
    "EXERCISE": "УПРАЖНЕНИЕ",
    "EXERCISES": "УПРАЖНЕНИЯ",
    "EXERCISE PROGRAM": "ПРОГРАММА УПРАЖНЕНИЙ",
    "EXERCISE PROGRAMS": "ПРОГРАММЫ УПРАЖНЕНИЙ",
    "EXERCISE INSTRUCTION": "ИНСТРУКЦИЯ ПО УПРАЖНЕНИЯМ",
    "EXERCISE EDUCATION": "ОБУЧЕНИЕ УПРАЖНЕНИЯМ",
}


def normalize_caps_heading(text: str) -> str:
    """
    Нормализует заголовок в капсе для лучшего перевода.
    Убирает лишние пробелы, нормализует числа.
    """
    # Убираем множественные пробелы
    text = re.sub(r"\s+", " ", text.strip())
    
    # Нормализуем числа в конце: "ACTIVITIES 33" → "ACTIVITIES"
    # Сохраняем число отдельно для восстановления
    number_match = re.search(r"\s+(\d+)\s*$", text)
    number = number_match.group(1) if number_match else None
    text_without_number = re.sub(r"\s+\d+\s*$", "", text)
    
    return text_without_number, number


def translate_heading_with_dictionary(text: str) -> str | None:
    """
    Переводит заголовок через словарь, если есть совпадение.
    """
    # Нормализуем: убираем лишние пробелы, приводим к верхнему регистру
    normalized = re.sub(r"\s+", " ", text.strip().upper())
    
    # Извлекаем число если есть
    number_match = re.search(r"\s+(\d+)\s*$", normalized)
    number = number_match.group(1) if number_match else None
    text_without_number = re.sub(r"\s+\d+\s*$", "", normalized)
    
    # Ищем точное совпадение
    if text_without_number in HEADING_DICTIONARY:
        translated = HEADING_DICTIONARY[text_without_number]
        if number:
            return f"{translated} {number}"
        return translated
    
    # Ищем частичное совпадение (для составных заголовков)
    for en_heading, ru_heading in HEADING_DICTIONARY.items():
        if text_without_number.startswith(en_heading):
            # Заменяем начало
            remainder = text_without_number[len(en_heading):].strip()
            if remainder:
                # Оставляем остаток для перевода через NLLB
                return f"{ru_heading} {remainder}"
            else:
                translated = ru_heading
                if number:
                    return f"{translated} {number}"
                return translated
    
    return None


def post_process_heading_translation(original_en: str, translated_ru: str) -> str:
    """
    Пост-обработка перевода заголовка для исправления артефактов.
    """
    # Если перевод выглядит как артефакт (слишком короткий, странные символы)
    if len(translated_ru) < len(original_en) * 0.3:
        # Слишком короткий - возможно артефакт
        # Пробуем словарь
        dict_translation = translate_heading_with_dictionary(original_en)
        if dict_translation:
            return dict_translation
    
    # Исправляем частые артефакты в заголовках
    s = translated_ru
    
    # "СОГЛАСНЫЕ УЧЕНИЕ" → проверяем через словарь
    if "СОГЛАСНЫЕ" in s and "УЧЕНИЕ" in s:
        dict_translation = translate_heading_with_dictionary(original_en)
        if dict_translation:
            return dict_translation
    
    # Убираем лишние пробелы
    s = re.sub(r"\s+", " ", s.strip())
    
    return s


def pre_process_heading_for_translation(text: str) -> str:
    """
    Pre-processing заголовка перед переводом для улучшения качества.
    """
    # Нормализуем капс: убираем лишние пробелы
    s = re.sub(r"\s+", " ", text.strip())
    
    # Если весь заголовок в капсе, пробуем словарь сначала
    if s.isupper() and len(s.split()) <= 5:
        dict_translation = translate_heading_with_dictionary(s)
        if dict_translation:
            return dict_translation
    
    # Для смешанного регистра - нормализуем
    # "CHAPTER 1" → оставляем как есть
    # "Chapter 1" → "CHAPTER 1" (для лучшего перевода)
    if not s.isupper() and re.match(r"^(chapter|part|section)\s+", s, re.IGNORECASE):
        s = s.upper()
    
    return s


def process_headings_in_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Обрабатывает заголовки в блоках: pre-processing и post-processing.
    Улучшенная версия: также проверяет по исходному тексту, если role не установлен.
    """
    processed = []
    
    for block in blocks:
        metadata = block.get("metadata", {})
        role = metadata.get("role", "")
        
        original_text = (block.get("text") or block.get("normalized_text") or "").strip()
        translated_text = (block.get("translated_text") or "").strip()
        
        # Определяем, является ли блок заголовком:
        # 1. По role (если установлен)
        # 2. По исходному тексту (если весь капс и короткий)
        is_heading = role in ("heading1", "heading2", "heading3")
        
        if not is_heading and original_text:
            # Проверяем по исходному тексту: если весь капс и короткий - вероятно заголовок
            if original_text.isupper() and len(original_text.split()) <= 6:
                is_heading = True
        
        if not is_heading:
            processed.append(block)
            continue
        
        if not original_text or not translated_text:
            processed.append(block)
            continue
        
        # Post-processing: исправляем перевод через словарь
        # Используем исходный текст для поиска в словаре
        improved = post_process_heading_translation(original_text, translated_text)
        
        # Если словарь не помог, но перевод выглядит как артефакт - пробуем еще раз
        if improved == translated_text and len(translated_text) < len(original_text) * 0.5:
            # Очень короткий перевод - точно артефакт
            dict_translation = translate_heading_with_dictionary(original_text)
            if dict_translation:
                improved = dict_translation
        
        # Обновляем блок
        new_block = dict(block)
        new_block["translated_text"] = improved
        processed.append(new_block)
    
    return processed

