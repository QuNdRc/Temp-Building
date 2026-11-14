"""Точное измерение геометрии плана: сетка, здание, запретная зона."""
from pathlib import Path
import cv2
import numpy as np
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLAN = Path(__file__).resolve().parent / "site_plan2.png"
img = cv2.imdecode(np.fromfile(str(PLAN), dtype=np.uint8), cv2.IMREAD_COLOR)
h, w = img.shape[:2]
B, G, R = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)

# --- сайтовая рамка (чёрная) ---
black = (R < 60) & (G < 60) & (B < 60)
ys, xs = np.where(black)
print("black bbox: x[%d,%d] y[%d,%d]" % (xs.min(), xs.max(), ys.min(), ys.max()))

# --- сетка: серые линии (исключая здание, которое тоже серое) ---
# сетка светло-серая ~207; здание может быть темнее/светлее
grid = (R >= 190) & (R <= 225) & (abs(R - G) < 15) & (abs(G - B) < 15)
# проекции
vsum = grid.sum(axis=0)
hsum = grid.sum(axis=1)

def peaks(arr, thresh):
    idx = [i for i, v in enumerate(arr) if v > thresh]
    out = []
    for i in idx:
        if out and i - out[-1] <= 4:
            out[-1] = (out[-1] + i) // 2  # сглаживаем
        else:
            out.append(i)
    return out

# порог: берём линии, где серого много (сетка ~ 500px высоты, здание ~ 180px)
vlines = peaks(vsum, 300)
hlines = peaks(hsum, 300)
print("vertical grid lines (px):", vlines)
print("horizontal grid lines (px):", hlines)

# --- здание: серый закрашенный прямоугольник (включая все оттенки серого) ---
building = (R >= 150) & (R <= 240) & (abs(R - G) < 20) & (abs(G - B) < 20)
bys, bxs = np.where(building)
print("\nbuilding gray bbox: x[%d,%d] y[%d,%d]" % (bxs.min(), bxs.max(), bys.min(), bys.max()))

# --- запретная зона: синяя ---
hazard = (B > 130) & (B > R + 30)
hys, hxs = np.where(hazard)
print("hazard blue bbox: x[%d,%d] y[%d,%d]" % (hxs.min(), hxs.max(), hys.min(), hys.max()))

# --- оранжевый (въезд?) ---
orange = (R > 150) & (G > 80) & (G < 160) & (B < 90)
oys, oxs = np.where(orange)
print("orange bbox: x[%d,%d] y[%d,%d]" % (oxs.min(), oxs.max(), oys.min(), oys.max()))
