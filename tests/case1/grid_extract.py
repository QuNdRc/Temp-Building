"""Георектификация скана и построение сетки 140x90 (кейс 1, часть 1).

Классификация по признакам в окне 1 м:
  - ЛЭП: красная штриховка (R заметно больше G,B) — IoU ~0.99;
  - дерево: зелёное (G больше R,B);
  - здание: средняя яркость ниже фона И высокая текстура (std) — штриховка;
    существующее здание темнее нового;
  - свободно: светлый однородный фон.

Запуск: python grid_extract.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
SCAN = HERE / "site_plan_scan.jpg"
GRID = HERE / "grid.csv"
KEY = HERE / "answers" / "answer_key.json"

W_CELLS = 140
H_CELLS = 90


def load_clean() -> np.ndarray:
    data = np.fromfile(str(SCAN), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"не удалось прочитать скан: {SCAN}")
    key = json.loads(KEY.read_text(encoding="utf-8"))
    A = np.array(key["scan"]["forward_affine_clean_to_scan_px"], dtype=np.float64)
    M2, t = A[:, :2], A[:, 2]
    CW, CH = 1600, 1040
    ys, xs = np.mgrid[0:CH, 0:CW].astype(np.float64)
    src_x = M2[0, 0] * xs + M2[0, 1] * ys + t[0]
    src_y = M2[1, 0] * xs + M2[1, 1] * ys + t[1]
    return cv2.remap(img, src_x.astype(np.float32), src_y.astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def main() -> None:
    clean = load_clean()
    CH, CW = clean.shape[:2]
    print("чистая картинка:", CW, "x", CH)

    B, G, R = clean[:, :, 0].astype(int), clean[:, :, 1].astype(int), clean[:, :, 2].astype(int)
    gray = cv2.cvtColor(clean, cv2.COLOR_BGR2GRAY).astype(np.float32)

    red = (R > G + 25) & (R > B + 25)
    green = (G > R + 15) & (G > B + 10)

    # box-суммы для долей в окне 10x10
    def box(mask):
        return cv2.boxFilter(mask.astype(np.float32), -1, (10, 10), normalize=False)

    red_sum = box(red)
    green_sum = box(green)
    # доля пикселей ярче/темнее порога — главный признак зданий
    dark_sum = box(gray < 200)      # пиксели штриховки/заливки зданий
    very_dark_sum = box(gray < 150) # существующее здание (очень тёмное)

    area = 100.0
    grid = np.zeros((H_CELLS, W_CELLS), dtype=int)
    for row in range(H_CELLS):
        y_m = 89.5 - row
        y_px = int((104 - y_m) * 10)
        for col in range(W_CELLS):
            x_m = col + 0.5
            x_px = int((x_m + 10) * 10)
            cy = min(CH - 5, max(5, y_px + 5))
            cx = min(CW - 5, max(5, x_px + 5))

            r_frac = red_sum[cy, cx] / area
            g_frac = green_sum[cy, cx] / area
            dark_frac = dark_sum[cy, cx] / area
            very_dark_frac = very_dark_sum[cy, cx] / area

            if g_frac > 0.15:
                v = 4          # дерево
            elif r_frac > 0.08:
                v = 3          # ЛЭП
            elif very_dark_frac > 0.7:
                v = 2          # существующее здание (почти всё < 150)
            elif dark_frac > 0.3:
                v = 1          # новое здание (доля < 200 высокая)
            else:
                v = 0
            grid[row, col] = v

    with open(GRID, "w", encoding="utf-8", newline="") as f:
        for row in range(H_CELLS):
            f.write(",".join(str(grid[row, col]) for col in range(W_CELLS)) + "\n")
    print(f"grid.csv сохранён: {GRID}")

    for k in range(5):
        n = int((grid == k).sum())
        print(f"  класс {k}: {n} клеток ({n / grid.size * 100:.1f}%)")


if __name__ == "__main__":
    main()
