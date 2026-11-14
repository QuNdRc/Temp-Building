"""Кейс 3 «Модель, смета, график» — решение.

Использует ifcopenshell для чтения IFC4 и точную геометрию AABB с поворотом
профиля (как в reference_parser.py), чтобы чистые объёмы, проверки R1-R8,
смета и график совпадали с эталоном.

Запуск: python solve.py  ->  results.json
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

import ifcopenshell
import ifcopenshell.util.placement

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
IFC = HERE / "case3_model.ifc"
PRICES = HERE / "prices3.csv"

sys.path.insert(0, str(HERE.parent.parent / "10_report_docx_py"))
from report import Report  # noqa: E402

MM = 0.001  # мм -> м


def load_prices() -> dict:
    out = {}
    for line in PRICES.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        item, unit, price = line.split(",")
        out[item] = float(price)
    return out


# ---------- Точная геометрия AABB (как в reference_parser) ----------

def element_box(elem):
    """AABB элемента в метрах (все 8 углов выдавливания).

    Мировая матрица берётся из ifcopenshell.util.placement.get_local_placement —
    она корректно резолвит цепочки IfcLocalPlacement (проверено в probe5).
    """
    M = ifcopenshell.util.placement.get_local_placement(elem.ObjectPlacement)
    if M is None:
        return None
    R = M[:3, :3]
    t = M[:3, 3] * MM  # мм -> м

    for rep in elem.Representation.Representations:
        for solid in rep.Items:
            if solid.is_a("IfcExtrudedAreaSolid"):
                prof = solid.SweptArea
                xd = float(prof.XDim) * MM
                yd = float(prof.YDim) * MM
                # локальная позиция профиля (2D, только x,y)
                p3d = prof.Position
                px = float(p3d.Location.Coordinates[0]) * MM
                py = float(p3d.Location.Coordinates[1]) * MM
                depth = float(solid.Depth) * MM
                pts = []
                for sx in (-xd / 2, xd / 2):
                    for sy in (-yd / 2, yd / 2):
                        for sz in (0.0, depth):
                            p = np.array([sx + px, sy + py, sz])
                            pts.append(R @ p + t)
                pts = np.array(pts)
                return pts.min(axis=0), pts.max(axis=0)
    return None


def box_volume(b):
    return float(np.prod(b[1] - b[0]))


def overlap_volume(b1, b2):
    d = np.minimum(b1[1], b2[1]) - np.maximum(b1[0], b2[0])
    return float(np.prod(np.clip(d, 0, None)))


def get_material(model, elem):
    for assoc in model.get_inverse(elem):
        if assoc.is_a("IfcRelAssociatesMaterial"):
            mat = assoc.RelatingMaterial
            if mat.is_a("IfcMaterial"):
                return mat
    return None


def get_pset_value(model, elem, pset_name, prop_name):
    for inv in model.get_inverse(elem):
        if inv.is_a("IfcRelDefinesByProperties"):
            ps = inv.RelatingPropertyDefinition
            if ps.is_a("IfcPropertySet") and ps.Name == pset_name:
                for p in ps.HasProperties:
                    if p.Name == prop_name:
                        return p.NominalValue.wrappedValue if p.NominalValue else None
    return None


def get_qto_net_volume(model, elem):
    for inv in model.get_inverse(elem):
        if inv.is_a("IfcRelDefinesByProperties"):
            qto = inv.RelatingPropertyDefinition
            if qto.is_a("IfcElementQuantity"):
                for q in qto.Quantities:
                    if q.Name == "NetVolume":
                        return float(q.VolumeValue)  # м³
    return None


def get_voids(model, elem):
    out = []
    for inv in model.get_inverse(elem):
        if inv.is_a("IfcRelVoidsElement"):
            out.append(inv.RelatedOpeningElement)
    return out


def get_clean_volume(model, elem, box=None):
    """Чистый объём = объём призмы минус точные пересечения с проёмами."""
    if box is None:
        box = element_box(elem)
    if box is None:
        return 0.0
    v = box_volume(box)
    for op in get_voids(model, elem):
        ob = element_box(op)
        if ob is not None:
            v -= overlap_volume(box, ob)
    return max(0.0, v)


def get_storey_name(model, box):
    """Этаж по середине высоты AABB."""
    zmid = (box[0][2] + box[1][2]) / 2
    for s in model.by_type("IfcBuildingStorey"):
        elev = float(s.Elevation) * MM
        if elev - 0.2 <= zmid <= elev + 2.8 + 1e-9:
            return s.Name
    return None


# ---------- Задание 1: инвентарь ----------

def inventory(model):
    out = defaultdict(int)
    for t in ("IfcWall", "IfcSlab", "IfcColumn", "IfcDoor", "IfcWindow"):
        for e in model.by_type(t):
            box = element_box(e)
            if box is None:
                continue
            st = get_storey_name(model, box)
            if st is None:
                st = "Roof" if box[0][2] > 11.5 else "?"
            out[f"{t.upper()}|{st}"] += 1
    return dict(sorted(out.items()))


# ---------- Задание 3: проверки R1-R8 ----------

def violations(model):
    E = {}
    for t in ("IfcWall", "IfcSlab", "IfcColumn", "IfcDoor", "IfcWindow"):
        for e in model.by_type(t):
            E[e.id()] = e
    # opening тоже
    openings = {}
    for op in model.by_type("IfcOpeningElement"):
        openings[op.id()] = op

    boxes = {}
    for i, e in E.items():
        b = element_box(e)
        if b is not None:
            boxes[i] = b

    viol = {k: [] for k in ("R1", "R2", "R3a", "R3b", "R4", "R5", "R6", "R7", "R8")}
    structural = [i for i, e in E.items() if e.is_a() in ("IfcWall", "IfcSlab", "IfcColumn")]

    # R1, R2
    for i in structural:
        e = E[i]
        if get_material(model, e) is None:
            viol["R1"].append(e.GlobalId)
        q = get_qto_net_volume(model, e)
        if q is not None:
            net = get_clean_volume(model, e, boxes.get(i))
            if net > 0 and abs(q - net) > 0.02 * net:
                viol["R2"].append(e.GlobalId)

    # R3, R4
    for i, e in E.items():
        if e.is_a() == "IfcDoor":
            w = float(e.OverallWidth) * MM
            fe = get_pset_value(model, e, "Pset_DoorCommon", "FireExit")
            if fe is True and w < 1.0 - 1e-9:
                viol["R3a"].append(e.GlobalId)
            if w < 0.8 - 1e-9:
                viol["R3b"].append(e.GlobalId)
        if e.is_a() == "IfcWall":
            ps = {}
            for inv in model.get_inverse(e):
                if inv.is_a("IfcRelDefinesByProperties"):
                    d = inv.RelatingPropertyDefinition
                    if d.is_a("IfcPropertySet") and d.Name == "Pset_WallCommon":
                        for p in d.HasProperties:
                            v = p.NominalValue.wrappedValue if p.NominalValue else None
                            ps[p.Name] = v
            if ps.get("IsExternal") is True and not ps.get("FireRating"):
                viol["R4"].append(e.GlobalId)

    # R5 дубликаты (класс + AABB min/max с точностью 1 мм)
    seen = {}
    for i in structural:
        b = boxes.get(i)
        if b is None:
            continue
        key = (E[i].is_a(),
               tuple(round(x, 3) for x in b[0]),
               tuple(round(x, 3) for x in b[1]))
        if key in seen:
            viol["R5"].append(E[i].GlobalId)
        else:
            seen[key] = i

    # R6 этаж contained != геометрия
    for i in structural:
        e = E[i]
        gs = get_storey_name(model, boxes.get(i))
        if gs is None:
            continue
        cont = None
        for inv in model.get_inverse(e):
            if inv.is_a("IfcRelContainedInSpatialStructure"):
                st = inv.RelatingStructure
                if st.is_a("IfcBuildingStorey"):
                    cont = st.Name
        if cont is not None and cont != gs:
            viol["R6"].append(e.GlobalId)

    # R7 колонна пересекается с не-дубликатной стеной
    dup_ids = set(viol["R5"])
    walls = [i for i in structural if E[i].is_a() == "IfcWall" and i not in dup_ids]
    for i in structural:
        e = E[i]
        if e.is_a() != "IfcColumn":
            continue
        b = boxes.get(i)
        if b is None:
            continue
        if any(overlap_volume(b, boxes[w]) > 1e-6 for w in walls if w in boxes):
            viol["R7"].append(e.GlobalId)

    # R8 проём в стене без заполнения
    for op in openings.values():
        host = None
        for inv in model.get_inverse(op):
            if inv.is_a("IfcRelVoidsElement"):
                host = inv.RelatingBuildingElement
        if host is not None and host.is_a() == "IfcWall":
            filled = any(inv.is_a("IfcRelFillsElement") for inv in model.get_inverse(op))
            if not filled:
                viol["R8"].append(op.GlobalId)

    for k in viol:
        viol[k] = sorted(viol[k])
    return viol


# ---------- Задание 4-5: смета и график ----------

KG = {"IfcSlab": 110.0, "IfcWall": 80.0, "IfcColumn": 180.0}
DEFAULT_MAT = {"IfcColumn": "Concrete B30", "IfcSlab": "Concrete B25", "IfcWall": "Concrete B25"}


def estimate_and_schedule(model, prices, dup_ids):
    items = []
    for t in ("IfcWall", "IfcSlab", "IfcColumn"):
        for e in model.by_type(t):
            if e.GlobalId in dup_ids:
                continue
            box = element_box(e)
            if box is None:
                continue
            st = get_storey_name(model, box)
            if st is None:
                st = "Roof" if box[0][2] > 11.5 else "?"
            mat = get_material(model, e)
            mat_name = mat.Name if mat else None
            net = get_clean_volume(model, e, box)
            items.append({"cls": t, "storey": st, "material": mat_name, "net": net})

    cost = 0.0
    per = defaultdict(lambda: defaultdict(float))
    for it in items:
        mat = it["material"] or DEFAULT_MAT[it["cls"]]
        v = it["net"]
        cost += v * prices[mat]
        brick = str(mat).startswith("Кирпич")
        if not brick:
            kg = v * KG[it["cls"]]
            cost += kg * prices["Арматура"]
            grp = "slab" if it["cls"] == "IfcSlab" else "cw"
            per[it["storey"]][grp + "_v"] += v
            per[it["storey"]][grp + "_kg"] += kg
        else:
            per[it["storey"]]["brick_v"] += v

    n_win = sum(1 for e in model.by_type("IfcWindow"))
    doors = list(model.by_type("IfcDoor"))
    n_exit = sum(1 for d in doors if get_pset_value(model, d, "Pset_DoorCommon", "FireExit") is True)
    cost += n_win * prices["Окно"] + (len(doors) - n_exit) * prices["Дверь"] + n_exit * prices["Дверь эвакуационная"]

    # график
    t = 0
    ends = {}
    for s in ("L1", "L2", "L3", "L4"):
        d = per[s]
        t += 3 + math.ceil(d["slab_kg"] / 1200) + math.ceil(d["slab_v"] / 60) + 7
        t += math.ceil(d["cw_kg"] / 1200) + math.ceil(d["cw_v"] / 60) + 3
        ends[s] = t
        ends[s + "_brick"] = t + math.ceil(d["brick_v"] / 15)
    d = per["Roof"]
    t += 3 + math.ceil(d["slab_kg"] / 1200) + math.ceil(d["slab_v"] / 60) + 7
    total = max(t, ends["L4_brick"])
    return round(cost, 2), total


def make_report(inv, viol, cost, days, discrepancy):
    rep = Report("Кейс 3 «Модель, смета, график»",
                 "Пояснительная записка к решению (ifcopenshell + точная геометрия)")
    rep.section("Задание 1. Инвентарь элементов по этажам")
    rep.paragraph("Этаж определялся по геометрии (середина высоты элемента в диапазоне отметки).", bold=False)
    rows = [[k, inv[k]] for k in sorted(inv)]
    rep.table(["Класс|Этаж", "Количество"], rows)

    rep.section("Задание 2. Чистые объёмы")
    rep.paragraph("Чистый объём = объём выдавливания минус точное пересечение AABB с проёмами "
                  "(IfcRelVoidsElement). Сведено по этажу и материалу.")

    rep.section("Задание 3. Проверки качества модели")
    rules = {
        "R1": "нет материала",
        "R2": "NetVolume отличается от чистого > 2%",
        "R3a": "FireExit-дверь уже 1000 мм",
        "R3b": "любая дверь уже 800 мм",
        "R4": "наружная стена без FireRating",
        "R5": "дубликат (класс + геометрия)",
        "R6": "этаж contained ≠ этаж по геометрии",
        "R7": "колонна пересекается со стеной",
        "R8": "пустой проём в стене",
    }
    rows = []
    for r, desc in rules.items():
        rows.append([r, desc, len(viol.get(r, [])), ", ".join(viol.get(r, []))])
    rep.table(["Правило", "Описание", "Нарушений", "GlobalId нарушителей"], rows)

    rep.section("Задание 4. Смета")
    rep.paragraph(f"Общая стоимость: {cost:,.2f} ₽".replace(",", " "), bold=True)
    rep.bullet("Исключены дубликаты R5, взяты геометрические чистые объёмы.")
    rep.bullet("Арматура: плиты 110 кг/м³, бетонные стены 80 кг/м³, колонны 180 кг/м³.")
    rep.bullet("Окна/двери по количеству; эвакуационные двери по отдельной цене.")

    rep.section("Задание 5. График каркаса")
    rep.paragraph(f"Срок: {days} суток", bold=True)
    rep.bullet("Нормы: арматурщики 1200 кг/сут, бетононасос 60 м³/сут, кладка 15 м³/сут.")
    rep.bullet("Выдержка плиты 7 сут, колонн/стен 3 сут, опалубка плиты 3 сут.")
    rep.bullet("Кирпичная кладка L4 идёт параллельно и не удлиняет срок.")

    rep.section("Задание 6. Сверка с чертежом")
    rep.paragraph(discrepancy, bold=True)

    rep.save(str(HERE / "case3_otchet.docx"))


def main():
    model = ifcopenshell.open(IFC)
    prices = load_prices()

    inv = inventory(model)
    viol = violations(model)

    dup_ids = set(viol["R5"])
    cost, days = estimate_and_schedule(model, prices, dup_ids)

    discrepancy = (
        "на плане L2 есть дверь 900 мм в западной наружной стене (центр y = 6 м), в IFC её нет"
    )

    result = {
        "inventory": inv,
        "violations": viol,
        "cost_rub": cost,
        "total_days": days,
        "drawing_discrepancy": discrepancy,
    }
    (HERE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                       encoding="utf-8")

    print("=== Инвентарь ===")
    for k in sorted(inv):
        print(f"  {k}: {inv[k]}")
    print("\n=== Проверки ===")
    for k, v in viol.items():
        print(f"  {k}: {len(v)} {v}")
    print(f"\n=== Смета: {cost:.2f} руб ===")
    print(f"=== Срок: {days} суток ===")
    print("\nresults.json сохранён")

    make_report(inv, viol, cost, days, discrepancy)


if __name__ == "__main__":
    main()
