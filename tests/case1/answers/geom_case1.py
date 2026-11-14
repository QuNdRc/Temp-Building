"""Точная геометрия кейса 1 (аналитически, без растеризации). Одна истина для генератора и проверяющего скрипта."""
import math

W, H = 140, 90
A = (18, 40, 62, 22)            # корпус 1: x, y, w, h
B = (96, 48, 38, 18)            # корпус 2
E = (100, 8, 30, 16)            # существующее здание
TREES = [(10, 20, 3.0), (14, 31, 3.5), (30, 9, 3.0), (86, 28, 3.5), (88, 36, 3.0)]
GATE = (62, 0, 8)
GATE_PT = (66.0, 0.0)
# охранная зона ЛЭП: всё, что выше прямой y = 74 + 6*x/140 (в пределах площадки)
LINE_Y0, LINE_SLOPE = 74.0, 6.0 / 140.0
POWER = [(0, 74), (140, 80), (140, 90), (0, 90)]

RCRANE = 65.0
CRANE_SIZE = 6.0
STORE_SIZE = [(12, 6), (14, 8), (10, 6)]
MATERIALS = ["арматура", "блоки и кирпич", "опалубка"]
LIFT_PTS = [(21, 43), (77, 43), (21, 59), (77, 59), (99, 51), (131, 63)]
CENTER1 = (A[0] + A[2] / 2, A[1] + A[3] / 2)
CENTER2 = (B[0] + B[2] / 2, B[1] + B[3] / 2)

BORDER = 3.0
CL_CRANE_NEW, CL_CRANE_E, CL_STORE = 4.0, 12.0, 1.0   # зазоры
CL_OBST = 1.0                                          # зазор до ЛЭП и деревьев (и крана, и складов)
CRANE_TO_STORE = 5.0
STORE_TO_STORE = 2.0


def rect_rect(a, b):
    dx = max(a[0] - (b[0] + b[2]), b[0] - (a[0] + a[2]), 0.0)
    dy = max(a[1] - (b[1] + b[3]), b[1] - (a[1] + a[3]), 0.0)
    return math.hypot(dx, dy)


def rect_circle(r, c):
    cx, cy, cr = c
    dx = max(r[0] - cx, 0.0, cx - (r[0] + r[2])); dy = max(r[1] - cy, 0.0, cy - (r[1] + r[3]))
    return max(math.hypot(dx, dy) - cr, 0.0)


def rect_power(r):
    """Расстояние от прямоугольника до зоны ЛЭП (полуплоскость выше прямой). 0 если пересекает."""
    x, y, w, h = r
    # наибольшая высота над прямой достигается в левом верхнем углу (прямая растёт вправо)
    height = (y + h) - (LINE_Y0 + LINE_SLOPE * x)
    if height >= 0:
        return 0.0
    return -height / math.sqrt(1 + LINE_SLOPE ** 2)


def in_border(r):
    return r[0] >= BORDER and r[1] >= BORDER and r[0] + r[2] <= W - BORDER and r[1] + r[3] <= H - BORDER


def crane_rect(c):
    return (c[0] - CRANE_SIZE / 2, c[1] - CRANE_SIZE / 2, CRANE_SIZE, CRANE_SIZE)


def center(r):
    return (r[0] + r[2] / 2, r[1] + r[3] / 2)


def crane_violations(c, R=RCRANE):
    v = []
    r = crane_rect(c)
    if not in_border(r): v.append("кран: ближе 3 м к границе или вне площадки")
    if rect_rect(r, A) < CL_CRANE_NEW or rect_rect(r, B) < CL_CRANE_NEW: v.append("кран: ближе 4 м к новому зданию")
    if rect_rect(r, E) < CL_CRANE_E: v.append("кран: ближе 12 м к существующему зданию")
    if rect_power(r) < CL_OBST: v.append("кран: зазор до ЛЭП меньше 1 м")
    if any(rect_circle(r, t) < CL_OBST for t in TREES): v.append("кран: зазор до дерева меньше 1 м")
    if any(math.hypot(c[0] - p[0], c[1] - p[1]) > R for p in LIFT_PTS): v.append("кран: не достаёт до точки подъёма")
    return v


def stores_violations(c, stores, R=RCRANE):
    v = []
    rects = [(s[0], s[1], w, h) for s, (w, h) in zip(stores, STORE_SIZE)]
    cr = crane_rect(c)
    for name, r in zip(MATERIALS, rects):
        if not in_border(r): v.append(f"склад {name}: ближе 3 м к границе или вне площадки")
        if any(rect_rect(r, o) < CL_STORE for o in (A, B, E)): v.append(f"склад {name}: зазор до здания меньше 1 м")
        if rect_power(r) < CL_OBST: v.append(f"склад {name}: зазор до ЛЭП меньше 1 м")
        if any(rect_circle(r, t) < CL_OBST for t in TREES): v.append(f"склад {name}: зазор до дерева меньше 1 м")
        cc = center(r)
        if math.hypot(cc[0] - c[0], cc[1] - c[1]) > R: v.append(f"склад {name}: центр вне вылета крана")
        if rect_rect(r, cr) < CRANE_TO_STORE: v.append(f"склад {name}: ближе 5 м к основанию крана")
    for i in range(3):
        for j in range(i):
            if rect_rect(rects[i], rects[j]) < STORE_TO_STORE:
                v.append(f"склады {MATERIALS[j]} и {MATERIALS[i]}: зазор меньше 2 м")
    return v


def cost(c, stores, deliv):
    """deliv: список (материал, рейсов/сут, подъёмов/сут, доля корпуса 1)"""
    tot = 0.0
    for s, (w, h), (_m, trips, lifts, sh) in zip(stores, STORE_SIZE, deliv):
        cc = (s[0] + w / 2, s[1] + h / 2)
        road = abs(cc[0] - GATE_PT[0]) + abs(cc[1] - GATE_PT[1])
        tot += trips * 2 * road
        d_cs = math.hypot(cc[0] - c[0], cc[1] - c[1])
        d_t = sh * math.hypot(c[0] - CENTER1[0], c[1] - CENTER1[1]) + (1 - sh) * math.hypot(c[0] - CENTER2[0], c[1] - CENTER2[1])
        tot += lifts * 3.0 * (d_cs + d_t) / 10.0
    return tot
