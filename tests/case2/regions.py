"""Точная раскраска регионов: серый вверху-справа vs цветной слева."""
from pathlib import Path
import cv2
import numpy as np
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLAN = Path(__file__).resolve().parent / "site_plan2.png"
img = cv2.imdecode(np.fromfile(str(PLAN), dtype=np.uint8), cv2.IMREAD_COLOR)

def show_region(name, x0, x1, y0, y1):
    region = img[y0:y1, x0:x1]
    flat = region.reshape(-1, 3).astype(int)
    avg = flat.mean(axis=0)
    uniq, counts = np.unique(flat, axis=0, return_counts=True)
    top = sorted(zip(uniq, counts), key=lambda z: -z[1])[:5]
    print(f"\n=== {name} [{x0}:{x1}, {y0}:{y1}] средний BGR={avg.astype(int)}")
    for c, n in top:
        print(f"    BGR{c} -> {n}px")

# серый прямоугольник вверху справа
show_region("СЕРЫЙ вверху-справа", 280, 520, 230, 360)
# цветной прямоугольник слева
show_region("ЦВЕТНОЙ слева", 100, 280, 360, 500)
# синяя полоска внизу
show_region("СИНЯЯ внизу", 430, 490, 555, 565)
# сетка-эталон
show_region("СЕТКА (фон)", 400, 420, 400, 420)
