"""Точные границы объектов по цветовым маскам + перевод в метры (10px/м)."""
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

def bbox(mask, name):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        print(name, "нет")
        return
    # px -> метры: сетка 10px/м, низ картинки y=560px это y=0м
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    mx0 = (x0 - 60) / 10.0
    mx1 = (x1 - 60) / 10.0
    my0 = (560 - y1) / 10.0
    my1 = (560 - y0) / 10.0
    print(f"{name}: px x[{x0},{x1}] y[{y0},{y1}]  ->  м x[{mx0:.2f},{mx1:.2f}] y[{my0:.2f},{my1:.2f}]  (w={mx1-mx0:.2f}, h={my1-my0:.2f})")

# здание: серый заливки (207), но НЕ линии сетки (тоже серые). Сетка — тонкие линии,
# здание — сплошная область. Берём серый с большим связным компонентом.
gray = (R >= 195) & (R <= 220) & (abs(R - G) < 12) & (abs(G - B) < 12)
num, labels = cv2.connectedComponents(gray.astype(np.uint8))
print("\nСерые компоненты (здание = крупнейший):")
comp_sizes = [(i, (labels == i).sum()) for i in range(1, num)]
comp_sizes.sort(key=lambda z: -z[1])
for i, s in comp_sizes[:5]:
    ys, xs = np.where(labels == i)
    print(f"  comp{i}: {s}px  x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}]")
biggest = comp_sizes[0][0]
building_mask = labels == biggest
bbox(building_mask, "\nЗДАНИЕ (крупный серый)")

# запретная зона: красная штриховка
red = (R > 140) & (G < 160) & (B < 110)
bbox(red, "ЗАПРЕТНАЯ ЗОНА (красная)")

# въезд: синий маркер
blue = (B > 140) & (R < 110) & (G < 160)
bbox(blue, "ВЪЕЗД (синий)")

# сетка
print("\nМасштаб: сетка 10px = 1м. Низ картинки (y=560px) = y=0м, лево (x=60px) = x=0м.")
