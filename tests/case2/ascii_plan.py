"""ASCII-карта плана: каждый символ = доминирующий цвет блока 10x10 px."""
from pathlib import Path
import cv2
import numpy as np
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLAN = Path(__file__).resolve().parent / "site_plan2.png"
img = cv2.imdecode(np.fromfile(str(PLAN), dtype=np.uint8), cv2.IMREAD_COLOR)
h, w = img.shape[:2]

def classify(bgr):
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    # белый фон
    if r > 245 and g > 245 and b > 245:
        return "."
    # синий — здание
    if b > 150 and b > r + 30:
        return "B"
    # оранжевый — запретная зона/сети
    if r > 150 and g > 80 and g < 160 and b < 90:
        return "O"
    # серый — сетка
    if abs(r - g) < 20 and abs(g - b) < 20 and 170 < r < 230:
        return "+"
    # чёрный — оси/рамка/текст
    if r < 60 and g < 60 and b < 60:
        return "#"
    return " "

# блоки 10x10
BH, BW = 10, 10
rows = h // BH
cols = w // BW
for i in range(rows):
    line = ""
    for j in range(cols):
        block = img[i*BH:(i+1)*BH, j*BW:(j+1)*BW].reshape(-1, 3)
        avg = block.mean(axis=0)
        line += classify(avg)
    print(f"{i*BH:3d} {line}")
print("     " + "".join(str((j*BW)//10 % 10) for j in range(cols)))
