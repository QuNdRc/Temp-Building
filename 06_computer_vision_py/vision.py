"""Компьютерное зрение для стройплощадки на OpenCV.

Запуск:  python vision.py image.jpg

Что умеет:
  * загрузить фото, перевести в серый;
  * найти контуры (дефекты, трещины, объекты);
  * отфильтровать мелкий шум;
  * посчитать площадь/периметр каждого дефекта;
  * нарисовать найденное и сохранить "до/после" для защиты.

Типичные кейсы: детект трещин, непрокрас фасада, отсутствие СИЗ (по контрасту),
мусор на площадке. Порог чувствительности подбирается под задачу.
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np


def detect_defects(img: np.ndarray, thresh: int = 60, min_area: int = 50) -> dict:
    """Ищет тёмные дефекты (трещины, выбоины) через адаптивный порог."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    # бинаризация: тёмное на светлом
    _, binary = cv2.threshold(blur, thresh, 255, cv2.THRESH_BINARY_INV)

    # морфология: убрать одиночные пиксели, связать разрывы трещин
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    defects = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        perimeter = cv2.arcLength(c, True)
        defects.append({
            "area": float(area),
            "perimeter": float(perimeter),
            "bbox": (int(x), int(y), int(w), int(h)),
            "circularity": float(4 * np.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0,
        })
    # крупные первыми
    defects.sort(key=lambda d: -d["area"])
    return {"binary": binary, "defects": defects, "gray": gray}


def annotate(img: np.ndarray, result: dict) -> np.ndarray:
    """Рисует найденные дефекты поверх фото."""
    out = img.copy()
    for i, d in enumerate(result["defects"]):
        x, y, w, h = d["bbox"]
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(out, f"#{i} {d['area']:.0f}px", (x, max(20, y - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    return out


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Детект дефектов по фото")
    ap.add_argument("image", help="путь к изображению")
    ap.add_argument("--thresh", type=int, default=60, help="порог бинаризации")
    ap.add_argument("--min-area", type=int, default=50, help="минимальная площадь")
    ap.add_argument("--out", default="06_vision_out.png")
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f"не удалось открыть изображение: {args.image}")
        return 1

    result = detect_defects(img, args.thresh, args.min_area)
    print(f"Размер фото: {img.shape[1]}x{img.shape[0]}")
    print(f"Найдено дефектов: {len(result['defects'])}")
    for i, d in enumerate(result["defects"][:20]):
        print(f"  #{i}: площадь={d['area']:.0f}px, периметр={d['perimeter']:.0f}, "
              f"циркулярность={d['circularity']:.2f} (1.0 = идеальный круг)")

    out = annotate(img, result)
    cv2.imwrite(args.out, out)
    print(f"\nКартинка с разметкой: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
