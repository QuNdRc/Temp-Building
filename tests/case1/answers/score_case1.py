#!/usr/bin/env python3
"""Проверка ответов по кейсу 1.

  python score_case1.py --grid my_grid.csv --placement my_placement.json [--deliveries deliveries.csv]

my_grid.csv       140 столбцов x 90 строк, значения 0..4, строка 0 = север (y = 90..89), столбец 0 = запад
my_placement.json {"crane": [cx, cy], "stores": [[x, y], [x, y], [x, y]]}
                  crane = центр основания (м); stores = левый нижний угол в порядке
                  арматура, блоки и кирпич, опалубка. Начало координат: юго-западный угол площадки.
Нужны рядом: geom_case1.py, grid_truth_1m.csv, answer_key.json.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import geom_case1 as G

NAMES = {0: "свободно", 1: "новое здание", 2: "существующее", 3: "ЛЭП", 4: "дерево"}


def load_deliv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((r["material"], float(r["trips_per_day"]), float(r["lifts_per_day"]), float(r["share_building1"])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid"); ap.add_argument("--placement")
    ap.add_argument("--deliveries", default=str(HERE / "deliveries.csv"))
    a = ap.parse_args()
    key = json.loads((HERE / "answer_key.json").read_text(encoding="utf-8"))

    if a.grid:
        truth = np.loadtxt(HERE / "grid_truth_1m.csv", delimiter=",", dtype=int)
        mine = np.loadtxt(a.grid, delimiter=",", dtype=int)
        assert mine.shape == truth.shape, f"размер {mine.shape}, ожидается {truth.shape}"
        print("ЧАСТЬ 1: IoU по классам")
        for c in range(1, 5):
            inter = np.logical_and(truth == c, mine == c).sum(); uni = np.logical_or(truth == c, mine == c).sum()
            print(f"  {c} {NAMES[c]:<14} IoU = {inter / uni if uni else 1.0:.3f}")
        print(f"  доля совпавших клеток = {(truth == mine).mean():.3f}")

    if a.placement:
        p = json.loads(Path(a.placement).read_text(encoding="utf-8"))
        c = tuple(p["crane"]); stores = [tuple(s) for s in p["stores"]]
        deliv = load_deliv(a.deliveries)
        viol = G.crane_violations(c) + G.stores_violations(c, stores)
        print("ЧАСТЬ 2:")
        if viol:
            print("  НАРУШЕНИЯ:"); [print("   -", v) for v in viol]
        else:
            print("  все ограничения выполнены")
        cost = G.cost(c, stores, deliv); ref = key["placement"]["reference_cost_grid_1m"]
        print(f"  cost = {cost:.1f}; эталон на сетке 1 м = {ref:.1f}; отношение = {cost / ref:.3f}"
              f" ({'допустимо' if not viol else 'недопустимое решение'})")


if __name__ == "__main__":
    main()
