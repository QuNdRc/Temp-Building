"""Детальная ASCII-карта зон интереса с шагом 4 px."""
from pathlib import Path
import cv2
import numpy as np
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLAN = Path(__file__).resolve().parent / "site_plan2.png"
img = cv2.imdecode(np.fromfile(str(PLAN), dtype=np.uint8), cv2.IMREAD_COLOR)

def classify(bgr):
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    if r > 245 and g > 245 and b > 245:
        return "."      # белый
    if r > 150 and b < 110 and g < 160:      # красный/розовый — запретная зона
        return "X"
    if b > 150 and r < 110 and g < 160:      # синий — въезд
        return "E"
    if abs(r - g) < 20 and abs(g - b) < 20:
        if 200 <= r <= 225:
            return "#"   # серый (здание или сетка)
        if r < 100:
            return "+"   # тёмно-серый/чёрный (оси, штриховка)
    return "?"

def dump(x0, x1, y0, y1, step, label):
    print(f"\n=== {label} (x[{x0}:{x1}], y[{y0}:{y1}], шаг {step}px) ===")
    for y in range(y0, y1, step):
        line = ""
        for x in range(x0, x1, step):
            px = img[y, x]
            line += classify(px)
        print(f"{y:4d} {line}")
    print("      " + "".join(str((x // step) % 10) for x in range(x0, x1, step)))

# здание (серый, вверху справа)
dump(320, 590, 230, 370, 4, "ЗДАНИЕ (серый)")
# запретная зона (красная, слева)
dump(90, 290, 350, 510, 4, "ЗАПРЕТНАЯ ЗОНА (красная)")
# въезд (синий, внизу)
dump(420, 500, 545, 570, 2, "ВЪЕЗД (синий)")
