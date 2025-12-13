from __future__ import annotations

from typing import List, Dict, Any
import math


def detect_columns(blocks: List[Dict[str, Any]], page_width: float) -> Dict[str, Any]:
    """
    Простая гистограммная детекция колонок по X-координатам центров блоков.
    Возвращает:
      {
        "columns": [ (x0, x1), ... ],
        "assignments": {block_id: column_index}
      }
    """
    if not blocks:
        return {"columns": [], "assignments": {}}

    centers = []
    for b in blocks:
        bbox = b.get("bbox") or {}
        x0, x1 = bbox.get("x0", 0), bbox.get("x1", 0)
        if x1 <= x0:
            continue
        cx = (x0 + x1) / 2.0
        centers.append(cx)

    if not centers:
        return {"columns": [], "assignments": {}}

    # Грубая гистограмма по ширине страницы
    bins = max(3, min(12, int(math.sqrt(len(centers)))))  # ограничим разумно
    hist = [0] * bins
    bin_width = page_width / bins
    for cx in centers:
        idx = min(bins - 1, max(0, int(cx / bin_width)))
        hist[idx] += 1

    # Пороги: пиковые корзины считаем колонками
    max_count = max(hist)
    threshold = max_count * 0.3  # эвристика
    columns = []
    in_peak = False
    start = 0
    for i, cnt in enumerate(hist):
        if cnt >= threshold and not in_peak:
            start = i
            in_peak = True
        if cnt < threshold and in_peak:
            end = i
            in_peak = False
            columns.append((start * bin_width, end * bin_width))
    if in_peak:
        columns.append((start * bin_width, bins * bin_width))

    # Если не нашли явных колонок, считаем одна колонка
    if not columns:
        columns = [(0.0, page_width)]

    # Назначаем блоки в ближайшую колонку
    assignments = {}
    for b in blocks:
        bbox = b.get("bbox") or {}
        x0, x1 = bbox.get("x0", 0), bbox.get("x1", 0)
        if x1 <= x0:
            continue
        cx = (x0 + x1) / 2.0
        best_idx = 0
        best_dist = 1e9
        for idx, (c0, c1) in enumerate(columns):
            mid = (c0 + c1) / 2.0
            dist = abs(cx - mid)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        assignments[b.get("id") or b.get("block_id") or ""] = best_idx

    return {"columns": columns, "assignments": assignments}


