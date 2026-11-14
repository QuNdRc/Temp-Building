"""Геометрические примитивы на shapely: пересечения, площади, расстояния,
bounding boxes — база для планировок, стройгенплана, раскроя и упаковки.

Запуск:  python geometry.py

Что здесь есть:
  * строить полигоны (комнаты, зоны, плиты) из координат;
  * пересечения (сколько плитка попадает в комнату, кран достаёт до зоны);
  * площади и расстояния;
  * упаковка прямоугольников (заготовка под раскрой панелей);
  * проверка покрытия: лежит ли объект внутри участка.
"""

from __future__ import annotations

import sys
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union


def rect(cx: float, cy: float, w: float, h: float) -> Polygon:
    """Прямоугольник с центром (cx, cy), шириной w, высотой h."""
    hw, hh = w / 2.0, h / 2.0
    return Polygon([(cx - hw, cy - hh), (cx + hw, cy - hh),
                    (cx + hw, cy + hh), (cx - hw, cy + hh)])


def intersection_area(a: Polygon, b: Polygon) -> float:
    """Площадь пересечения двух полигонов."""
    return a.intersection(b).area


def distance(a, b) -> float:
    """Минимальное расстояние между геометриями."""
    return a.distance(b)


def coverage(zone: Polygon, items: list[Polygon]) -> dict:
    """Покрытие зоны объектами: общая площадь, наложение, покрытая доля."""
    total = zone.area
    union = unary_union([zone.intersection(i) for i in items])
    return {
        "zone_area": total,
        "covered_area": union.area,
        "covered_fraction": union.area / total if total > 0 else 0.0,
    }


def bin_pack(rects: list[tuple[float, float]], width: float) -> list[Polygon]:
    """Простая упаковка прямоугольников (w,h) в полосу шириной width —
    алгоритм "нижний левый" (Bottom-Left). Возвращает полигоны упакованных мест.
    Для настоящего раскроя замени на оптимизацию из 01_optimization_cpp."""
    placed: list[Polygon] = []
    height = 0.0
    x, y, row_h = 0.0, 0.0, 0.0
    for w, h in sorted(rects, key=lambda r: -r[1]):  # высокие первыми
        if x + w > width:  # новая строка
            x, y, row_h = 0.0, y + row_h, 0.0
        placed.append(Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)]))
        x += w
        row_h = max(row_h, h)
        height = max(height, y + row_h)
    return placed


def plot(polys: list[Polygon], out: str, title: str = "") -> None:
    """Картинка с полигонами — для защиты."""
    fig, ax = plt.subplots(figsize=(8, 6))
    for p in polys:
        if p.is_empty:
            continue
        xs, ys = p.exterior.xy
        ax.fill(xs, ys, alpha=0.4, edgecolor="black")
    ax.set_aspect("equal")
    ax.set_title(title)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # --- демо: стройгенплан ---
    site = rect(0, 0, 60, 40)              # участок 60x40
    crane = Point(10, 10)                  # кран
    crane_reach = crane.buffer(22)         # вылет стрелы 22
    zone_a = rect(-15, 0, 20, 15)          # склад
    zone_b = rect(15, 5, 25, 20)           # монтажная зона

    print("=== Стройгенплан ===")
    print("Площадь участка:", site.area)
    print("Склад дотягивается краном:", crane_reach.intersects(zone_a))
    print("Монтажная зона дотягивается:", crane_reach.intersects(zone_b))
    print("Расстояние кран->монтажная зона:", distance(crane, zone_b))

    print("\n=== Покрытие зоны ===")
    cov = coverage(zone_b, [rect(15, 5, 8, 6), rect(24, 8, 6, 6)])
    print(f"Зона покрыта на {cov['covered_fraction']*100:.1f}%")

    print("\n=== Раскрой панелей (упаковка в полосу 12) ===")
    pieces = [(5, 3), (4, 2), (3, 3), (6, 2), (2, 2), (4, 4)]
    packed = bin_pack(pieces, width=12)
    total_area = sum(w * h for w, h in pieces)
    print("Суммарная площадь деталей:", total_area)

    plot([site, crane_reach, zone_a, zone_b], "05_geometry_py_plot.png",
         "Стройгенплан: кран, зона вылета, склады")
    plot(packed, "05_geometry_py_pack.png", "Раскрой панелей")
    print("\nКартинки: 05_geometry_py_plot.png, 05_geometry_py_pack.png")


if __name__ == "__main__":
    main()
