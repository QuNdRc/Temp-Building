#!/usr/bin/env python3
"""python score_case3.py results.json   (рядом: answer_key3.json, reference_parser.py, case3_model.ifc)"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reference_parser as M

mine = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ref = M.reference_solution(str(HERE / "case3_model.ifc"))

if "inventory" in mine:
    ri = {k: v for k, v in ref["inventory_by_geometric_storey"].items()}
    ok = ri == mine["inventory"]
    print("1. инвентарь:", "совпал" if ok else "НЕ совпал")
    if not ok:
        for k in sorted(set(ri) | set(mine["inventory"])):
            if ri.get(k) != mine["inventory"].get(k): print(f"   {k}: у тебя {mine['inventory'].get(k)}, эталон {ri.get(k)}")
if "violations" in mine:
    print("3. правила:")
    for r, exp in ref["violations"].items():
        got = sorted(mine["violations"].get(r, []))
        ok = got == sorted(exp)
        print(f"   {r}: {'ок' if ok else 'НЕТ'}  (у тебя {len(got)}, эталон {len(exp)})")
if "cost_rub" in mine:
    d = abs(mine["cost_rub"] - ref["cost_rub"]) / ref["cost_rub"]
    print(f"4. смета: {mine['cost_rub']:.0f} против {ref['cost_rub']:.0f} ({d * 100:.2f}%) -> {'ок' if d <= 0.005 else 'НЕТ'}")
if "total_days" in mine:
    print(f"5. срок: {mine['total_days']} против {ref['total_days']} -> {'ок' if mine['total_days'] == ref['total_days'] else 'НЕТ'}")
print("6. чертёж: сверь текст с answer_key3.json -> drawing_discrepancy")
