"""Решение кейса 2 «Бытовой городок» (лёгкий).

Три части:
  1) CV: читаем site_plan2.png, находим здание, запретную зону, въезд
     (калибровка по сетке: 10 px = 1 м, начало координат — юго-западный угол).
  2) Расставляем три бытовки 6x3 (целые координаты, без поворота) с учётом
     всех ограничений, минимизируя сумму d(центр, въезд) + d(центр, вход).
  3) CPM по works2.csv: срок, критический путь, резервы, чувствительность
     к задержкам «Фундамент» и «Ввод коммуникаций».

Запуск:  python solve.py
На выходе: текстовый отчёт + plan_solution.png (картинка для защиты).
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import cv2
import numpy as np

# генератор ПЗ лежит в соседней заготовке
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "10_report_docx_py"))
from report import Report  # noqa: E402

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
PLAN = HERE / "site_plan2.png"
WORKS = HERE / "works2.csv"

SITE_W, SITE_H = 80.0, 50.0
CABIN_W, CABIN_H = 6.0, 3.0
GATE = (40.0, 0.0)       # въезд
ENTRANCE = (40.0, 20.0)  # вход в здание
CORRIDOR = (37.0, 0.0, 6.0, 20.0)  # проезд x[37,43], y[0,20]


# ================= Часть 1. Чтение плана =================

def read_plan() -> dict:
    """Определяет геометрию по картинке через цветовые маски + калибровку сетки."""
    data = np.fromfile(str(PLAN), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"не удалось прочитать план: {PLAN}")
    h, w = img.shape[:2]
    B, G, R = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)

    # калибровка: сетка — серые линии, шаг 10 px/м
    grid = (R >= 190) & (R <= 225) & (abs(R - G) < 15) & (abs(G - B) < 15)
    vsum = grid.sum(axis=0)
    hsum = grid.sum(axis=1)

    def peaks(arr, thresh):
        cand = [i for i, v in enumerate(arr) if v > thresh]
        out = []
        for i in cand:
            if out and i - out[-1] <= 6:
                out[-1] = (out[-1] + i) // 2  # сглаживаем близкие пиксели линии
            else:
                out.append(i)
        return out

    vlines = peaks(vsum, 300)
    hlines = peaks(hsum, 300)
    # ось x=0 — самая левая вертикальная линия, ось y=0 — самая нижняя горизонтальная
    x0_px = vlines[0]
    y0_px = hlines[-1]
    ppm = float(vlines[1] - vlines[0]) / 10.0

    def to_m(x0, x1, y0, y1):
        return {
            "x": round((x0 - x0_px) / ppm, 2),
            "y": round((y0_px - y1) / ppm, 2),   # инверсия: низ картинки = юг
            "w": round((x1 - x0) / ppm, 2),      # ширина = x1 - x0 (без +1)
            "h": round((y1 - y0) / ppm, 2),
        }

    def largest(mask):
        num, labels = cv2.connectedComponents(mask.astype(np.uint8))
        if num <= 1:
            return None
        best, best_sz = 1, 0
        for i in range(1, num):
            s = int((labels == i).sum())
            if s > best_sz:
                best, best_sz = i, s
        ys, xs = np.where(labels == best)
        return to_m(int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()))

    # здание — серый заливки; расширяем на 2 px, чтобы захватить чёрную обводку
    bmask = (R >= 195) & (R <= 220) & (abs(R - G) < 12) & (abs(G - B) < 12)
    bmask = cv2.dilate(bmask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    building = largest(bmask)
    # запретная зона — красная штриховка
    hazard = largest((R > 140) & (G < 160) & (B < 110))
    # въезд — синий маркер; диапазон x «от и до» включительно
    blue = (B > 140) & (R < 110) & (G < 160)
    ys, xs = np.where(blue)
    gate_x = None
    if len(xs):
        gate_x = round((int(xs.min()) - x0_px) / ppm, 2), round((int(xs.max()) + 1 - x0_px) / ppm, 2)

    return {"building": building, "hazard": hazard, "gate_x": gate_x,
            "px_per_m": ppm, "origin": (x0_px, y0_px), "image": (w, h)}


# ================= Часть 2. Бытовки =================

def cabin_cost(cx: float, cy: float) -> float:
    return math.hypot(cx - GATE[0], cy - GATE[1]) + math.hypot(cx - ENTRANCE[0], cy - ENTRANCE[1])


def gap(a, b) -> float:
    """Зазор между прямоугольниками (x,y,w,h); <0 — пересекаются."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(ax, bx) - min(ax + aw, bx + bw)
    dy = max(ay, by) - min(ay + ah, by + bh)
    if dx <= 0 and dy <= 0:
        return -min(-dx, -dy)
    if dx > 0 and dy > 0:
        return math.hypot(dx, dy)
    return max(dx, dy)


def single_valid(x: int, y: int, plan: dict) -> bool:
    """Ограничения 1, 2, 4 для одной бытовки."""
    if x < 2 or y < 2 or x + CABIN_W > SITE_W - 2 or y + CABIN_H > SITE_H - 2:
        return False
    for b in (plan["building"], plan["hazard"]):
        if b and gap((x, y, CABIN_W, CABIN_H), (b["x"], b["y"], b["w"], b["h"])) < 1:
            return False
    # проезд должен остаться свободным (не пересекаем)
    if gap((x, y, CABIN_W, CABIN_H), CORRIDOR) < 0:
        return False
    return True


def solve_cabins(plan: dict) -> dict:
    """Точный перебор: отбираем дешёвые допустимые клетки, ищем лучшую тройку."""
    cells = []
    for x in range(2, int(SITE_W) - int(CABIN_W) - 1):
        for y in range(2, int(SITE_H) - int(CABIN_H) - 1):
            if not single_valid(x, y, plan):
                continue
            cx, cy = x + CABIN_W / 2, y + CABIN_H / 2
            c = cabin_cost(cx, cy)
            if c <= 27.0:  # заведомо хватает для оптимума
                cells.append((c, x, y))
    cells.sort()

    best, best_pos = None, None
    n = len(cells)
    for a in range(n):
        xa, ya = cells[a][1], cells[a][2]
        for b in range(a + 1, n):
            xb, yb = cells[b][1], cells[b][2]
            if gap((xa, ya, CABIN_W, CABIN_H), (xb, yb, CABIN_W, CABIN_H)) < 1:
                continue
            cab = cells[a][0] + cells[b][0]
            if best is not None and cab >= best:
                continue
            for c in range(b + 1, n):
                xc, yc = cells[c][1], cells[c][2]
                if gap((xa, ya, CABIN_W, CABIN_H), (xc, yc, CABIN_W, CABIN_H)) < 1:
                    continue
                if gap((xb, yb, CABIN_W, CABIN_H), (xc, yc, CABIN_W, CABIN_H)) < 1:
                    continue
                total = cab + cells[c][0]
                if best is None or total < best:
                    best = total
                    best_pos = [(xa, ya), (xb, yb), (xc, yc)]
    return {"positions": best_pos, "cost": round(best, 4) if best is not None else None}


# ================= Часть 3. График (CPM) =================

def read_works() -> list[dict]:
    with open(WORKS, encoding="utf-8", newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            preds = [p for p in (r["preds"].split(",") if r["preds"].strip() else []) if p]
            rows.append({"id": r["id"], "name": r["name"], "preds": preds, "days": int(r["days"])})
    return rows


def cpm(works: list[dict]) -> dict:
    """CPM: прямой проход (ES), обратный проход (LF), резервы, критический путь.
    CSV задан в топологическом порядке, поэтому обратный проход идём с конца."""
    ids = [w["id"] for w in works]
    idx = {i: k for k, i in enumerate(ids)}
    n = len(works)

    # прямой проход: ES[i] = max(EF предшественников)
    es = [0] * n
    for i, w in enumerate(works):
        for p in w["preds"]:
            es[i] = max(es[i], es[idx[p]] + works[idx[p]]["days"])
    ef = [es[i] + works[i]["days"] for i in range(n)]
    total = max(ef)

    # successors для обратного прохода
    succ = [[] for _ in range(n)]
    for i, w in enumerate(works):
        for p in w["preds"]:
            succ[idx[p]].append(i)

    # обратный проход: LF[i] = min(LS последователей) = min(LF[j] - dur[j])
    lf = [total] * n
    for i in reversed(range(n)):
        for j in succ[i]:
            lf[i] = min(lf[i], lf[j] - works[j]["days"])

    slack = [lf[i] - ef[i] for i in range(n)]  # резерв = LF - EF
    critical = [works[i]["id"] for i in range(n) if abs(slack[i]) < 1e-9]
    return {"total": total, "es": es, "ef": ef, "lf": lf, "slack": slack,
            "critical": critical, "works": works, "idx": idx}


def with_delay(works: list[dict], target: str, delta: int) -> dict:
    w2 = [dict(w) for w in works]
    for w in w2:
        if w["id"] == target:
            w["days"] += delta
    return cpm(w2)


# ================= Визуализация =================

def draw(plan: dict, positions, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=130)
    ax.set_xlim(-2, SITE_W + 2)
    ax.set_ylim(-2, SITE_H + 2)
    ax.set_aspect("equal")
    ax.grid(True, color="#cccccc", linewidth=0.4)
    ax.set_xticks(range(0, 81, 10))
    ax.set_yticks(range(0, 51, 10))
    ax.set_title("Бытовой городок — план размещения", fontsize=13, pad=12)
    ax.set_xlabel("x, м")
    ax.set_ylabel("y, м")

    # площадка
    ax.add_patch(Rectangle((0, 0), SITE_W, SITE_H, fill=False,
                           edgecolor="black", linewidth=2))

    b = plan["building"]
    if b:
        ax.add_patch(Rectangle((b["x"], b["y"]), b["w"], b["h"],
                               facecolor="#9e9e9e", edgecolor="black", label="Здание"))
        ax.text(b["x"] + b["w"] / 2, b["y"] + b["h"] / 2,
                f"Здание\n{b['w']:.0f}×{b['h']:.0f} м\n{b['w']*b['h']:.0f} м²",
                ha="center", va="center", fontsize=9, color="black", fontweight="bold")
    hz = plan["hazard"]
    if hz:
        ax.add_patch(Rectangle((hz["x"], hz["y"]), hz["w"], hz["h"],
                               facecolor="#e57373", alpha=0.55,
                               edgecolor="#b71c1c", hatch="//", label="Запретная зона (сети)"))
        ax.text(hz["x"] + hz["w"] / 2, hz["y"] + hz["h"] / 2,
                f"Сети\n{hz['w']:.0f}×{hz['h']:.0f} м\n{hz['w']*hz['h']:.0f} м²",
                ha="center", va="center", fontsize=8, color="#7f0000", fontweight="bold")
    # проезд
    cx, cy, cw, ch = CORRIDOR
    ax.add_patch(Rectangle((cx, cy), cw, ch, facecolor="#fff59d", alpha=0.5,
                           edgecolor="#f9a825", linestyle="--", label="Проезд (свободен)"))

    # въезд и вход
    ax.plot(*GATE, marker="v", color="#1565c0", markersize=14, label="Въезд (40,0)")
    ax.plot(*ENTRANCE, marker="^", color="#1565c0", markersize=14, label="Вход в здание (40,20)")

    colors = ["#2e7d32", "#43a047", "#66bb6a"]
    for i, (x, y) in enumerate(positions):
        ax.add_patch(Rectangle((x, y), CABIN_W, CABIN_H,
                               facecolor=colors[i % 3], edgecolor="#1b5e20",
                               linewidth=1.5, label=f"Бытовка {i+1} ({x},{y})"))
        cx_, cy_ = x + CABIN_W / 2, y + CABIN_H / 2
        ax.plot([cx_, GATE[0]], [cy_, GATE[1]], color="#616161", linewidth=0.7, alpha=0.7)
        ax.plot([cx_, ENTRANCE[0]], [cy_, ENTRANCE[1]], color="#616161", linewidth=0.7, alpha=0.7)
        ax.text(cx_, cy_, f"{i+1}", ha="center", va="center", fontsize=9,
                fontweight="bold", color="white")

    # подпись итоговой стоимости
    total = sum(cabin_cost(x + CABIN_W / 2, y + CABIN_H / 2) for x, y in positions)
    ax.text(0.02, 0.98, f"Сумма расстояний: {total:.2f} м",
            transform=ax.transAxes, va="top", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#333", alpha=0.9))

    ax.legend(loc="upper left", fontsize=8, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ================= Главное =================

def main() -> None:
    plan = read_plan()
    print("=== Часть 1. Прочитать план ===")
    b = plan["building"]
    hz = plan["hazard"]
    print(f"Здание: x={b['x']}, y={b['y']}, ширина={b['w']}, высота={b['h']} "
          f"-> площадь {b['w']*b['h']:.1f} м2")
    print(f"Запретная зона: x={hz['x']}, y={hz['y']}, ширина={hz['w']}, высота={hz['h']} "
          f"-> площадь {hz['w']*hz['h']:.1f} м2")
    if plan["gate_x"]:
        print(f"Въезд по x: от {plan['gate_x'][0]} до {plan['gate_x'][1]}")
    print(f"(масштаб {plan['px_per_m']:.2f} px/м)")

    print("\n=== Часть 2. Три бытовки ===")
    sol = solve_cabins(plan)
    print("Позиции (x,y):", sol["positions"])
    print("Сумма расстояний:", sol["cost"])

    print("\n=== Часть 3. График ===")
    works = read_works()
    r = cpm(works)
    print(f"Общий срок: {r['total']} дней")
    print("Критический путь:", " -> ".join(r["critical"]))
    for i, w in enumerate(works):
        print(f"  {w['id']} ({w['name']}): резерв {r['slack'][i]} дн")
    print("\nЧувствительность:")
    print("  Фундамент +3 дня   -> срок", with_delay(works, "E", 3)["total"])
    print("  Ввод коммуникаций +8 -> срок", with_delay(works, "H", 8)["total"])
    print("  Ввод коммуникаций +20 -> срок", with_delay(works, "H", 20)["total"])

    draw(plan, sol["positions"], HERE / "plan_solution.png")
    print("\nКартинка сохранена: plan_solution.png")

    make_report(plan, sol, r, works)


def make_report(plan: dict, sol: dict, r: dict, works: list[dict]) -> None:
    """Собирает пояснительную записку в Word."""
    b = plan["building"]
    hz = plan["hazard"]
    rep = Report("Кейс 2 «Бытовой городок»",
                 "Пояснительная записка к решению")
    rep.section("Часть 1. Чтение плана")
    rep.table(["Объект", "x, м", "y, м", "Ширина, м", "Высота, м", "Площадь, м²"],
              [["Здание", b["x"], b["y"], b["w"], b["h"], f"{b['w']*b['h']:.0f}"],
               ["Запретная зона (сети)", hz["x"], hz["y"], hz["w"], hz["h"], f"{hz['w']*hz['h']:.0f}"]])
    if plan["gate_x"]:
        rep.paragraph(f"Въезд по оси x: от {plan['gate_x'][0]} до {plan['gate_x'][1]} м")

    rep.section("Часть 2. Размещение бытовок")
    rep.table(["№", "x, м", "y, м"],
              [[i + 1, x, y] for i, (x, y) in enumerate(sol["positions"])])
    rep.paragraph(f"Сумма расстояний (центр–въезд + центр–вход): {sol['cost']:.3f} м", bold=True)

    rep.section("Часть 3. График производства работ")
    rep.paragraph(f"Общий срок: {r['total']} дней", bold=True)
    rep.paragraph("Критический путь: " + " → ".join(r["critical"]))
    rep.table(["ID", "Работа", "ES", "EF", "LF", "Резерв, дн"],
              [[w["id"], w["name"], r["es"][i], r["ef"][i], r["lf"][i], r["slack"][i]]
               for i, w in enumerate(works)])
    rep.paragraph("Чувствительность к задержкам:")
    rep.bullet(f"Фундамент +3 дня → срок {with_delay(works, 'E', 3)['total']} дн")
    rep.bullet(f"Ввод коммуникаций +8 дн → срок {with_delay(works, 'H', 8)['total']} дн")
    rep.bullet(f"Ввод коммуникаций +20 дн → срок {with_delay(works, 'H', 20)['total']} дн")

    rep.section("Приложение. План размещения")
    rep.image(str(HERE / "plan_solution.png"), "Рис. 1 — план площадки с бытовками", width_in=6.3)

    rep.save(str(HERE / "case2_otchet.docx"))


if __name__ == "__main__":
    main()
