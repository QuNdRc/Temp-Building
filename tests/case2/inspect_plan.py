"""Быстрый анализ плана: выводит цветные области, сетку и масштаб."""
from pathlib import Path
import cv2
import numpy as np
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLAN = Path(__file__).resolve().parent / "site_plan2.png"
data = np.fromfile(str(PLAN), dtype=np.uint8)
img = cv2.imdecode(data, cv2.IMREAD_COLOR)
h, w = img.shape[:2]
print("image", w, "x", h)

def region(name, lo, hi):
    m = cv2.inRange(img, np.array(lo, np.uint8), np.array(hi, np.uint8))
    n = int((m > 0).sum())
    print(f"\n=== {name}: {n} px")
    if n == 0:
        return
    ys, xs = np.where(m > 0)
    print(f"  bbox: x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}]")
    num, labels = cv2.connectedComponents(m)
    print(f"  connected components: {num - 1}")
    for i in range(1, num):
        yy, xx = np.where(labels == i)
        if len(xx) < 20:
            continue
        print(f"    comp{i}: x[{xx.min()},{xx.max()}] y[{yy.min()},{yy.max()}] size={len(xx)}")

# синие оттенки (здание?)
region("BLUE", (40, 50, 170), (110, 130, 230))
# оранжевые (запретная зона?)
region("ORANGE", (150, 85, 20), (225, 145, 85))
# серые линии сетки
region("GRAY-grid", (200, 200, 200), (214, 214, 214))
# чёрный (рамка/оси?)
region("BLACK", (0, 0, 0), (40, 40, 40))

# горизонтальные и вертикальные линии сетки: считаем по проекциям серого
m = cv2.inRange(img, np.array(190, np.uint8), np.array(230, np.uint8))
col = (m > 0).sum(axis=0)  # по столбцам
row = (m > 0).sum(axis=1)  # по строкам
cols = [i for i, v in enumerate(col) if v > 20]
rows = [i for i, v in enumerate(row) if v > 20]
# группируем подряд идущие
def groups(xs, gap=3):
    out = []
    if not xs:
        return out
    s = p = xs[0]
    for x in xs[1:]:
        if x - p <= gap:
            p = x
        else:
            out.append((s + p) // 2)
            s = p = x
    out.append((s + p) // 2)
    return out

gcols = groups(cols)
grows = groups(rows)
print("\n=== Сетка (вертикальные линии, x):", gcols)
print("=== Сетка (горизонтальные линии, y):", grows)
if len(gcols) >= 2:
    print("шаг сетки по x (px):", [gcols[i+1]-gcols[i] for i in range(min(len(gcols)-1, 10))])
if len(grows) >= 2:
    print("шаг сетки по y (px):", [grows[i+1]-grows[i] for i in range(min(len(grows)-1, 10))])
