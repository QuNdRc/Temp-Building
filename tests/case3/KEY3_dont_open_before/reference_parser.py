"""Мини-парсер IFC4 (STEP) и эталонные вычисления для кейса 3. Без внешних библиотек, кроме numpy."""
import math
import re
from collections import defaultdict

import numpy as np

# ------------------------------------------------------------------ STEP
class Ref(int):
    pass


class Enum(str):
    pass


class Typed:
    def __init__(self, name, val):
        self.name, self.val = name, val

    def __repr__(self):
        return f"{self.name}({self.val!r})"


def decode_str(s):
    s = s.replace("''", "'")
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", lambda m: bytes.fromhex(m.group(1)).decode("utf-16-be"), s)


def parse_value(s, i):
    while s[i].isspace():
        i += 1
    c = s[i]
    if c == "'":
        j = i + 1; buf = []
        while True:
            if s[j] == "'":
                if j + 1 < len(s) and s[j + 1] == "'":
                    buf.append("''"); j += 2; continue
                break
            buf.append(s[j]); j += 1
        return decode_str("".join(buf)), j + 1
    if c == "#":
        j = i + 1
        while s[j].isdigit(): j += 1
        return Ref(int(s[i + 1:j])), j
    if c == "$":
        return None, i + 1
    if c == "*":
        return "*", i + 1
    if c == "(":
        out = []; j = i + 1
        while True:
            while s[j].isspace(): j += 1
            if s[j] == ")": return out, j + 1
            v, j = parse_value(s, j); out.append(v)
            while s[j].isspace(): j += 1
            if s[j] == ",": j += 1
    if c == ".":
        j = s.index(".", i + 1)
        return Enum(s[i + 1:j]), j + 1
    m = re.compile(r"[-+]?\d+(\.\d*)?([eE][-+]?\d+)?").match(s, i)
    if m and (c.isdigit() or c in "+-"):
        t = m.group(0)
        return (float(t) if ("." in t or "e" in t.lower()) else int(t)), m.end()
    m = re.compile(r"[A-Z0-9_]+").match(s, i)
    name = m.group(0); j = m.end()
    v, j = parse_value(s, j)           # сразу за именем идёт ( ... )
    return Typed(name, v[0] if isinstance(v, list) and len(v) == 1 else v), j


def read_entities(text):
    data = text[text.index("DATA;") + 5: text.rindex("ENDSEC;")]
    stmts, buf, q = [], [], False
    for ch in data:
        if ch == "'": q = not q
        if ch == ";" and not q:
            stmts.append("".join(buf).strip()); buf = []
        else:
            buf.append(ch)
    ents = {}
    for st in stmts:
        m = re.match(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*(\(.*\))\s*$", st, re.S)
        if not m: continue
        args, _ = parse_value(m.group(3), 0)
        ents[int(m.group(1))] = (m.group(2), args)
    return ents


# ------------------------------------------------------------------ геометрия
def axis_mat(ents, ref):
    _, a = ents[ref]
    loc = np.array(ents[a[0]][1][0], float)
    z = np.array(ents[a[1]][1][0], float) if a[1] is not None else np.array([0, 0, 1.0])
    x = np.array(ents[a[2]][1][0], float) if a[2] is not None else np.array([1.0, 0, 0])
    z /= np.linalg.norm(z); x = x - z * x.dot(z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z]), loc


def placement(ents, ref, cache):
    if ref is None: return np.eye(3), np.zeros(3)
    if ref in cache: return cache[ref]
    _, a = ents[ref]
    Rp, tp = placement(ents, a[0], cache)
    Rl, tl = axis_mat(ents, a[1])
    out = (Rp @ Rl, Rp @ tl + tp)
    cache[ref] = out
    return out


def element_box(ents, el_ref, k, cache):
    """AABB (в метрах) по IfcExtrudedAreaSolid с прямоугольным профилем."""
    _, a = ents[el_ref]
    R, t = placement(ents, a[5], cache)
    pds = ents[a[6]][1]
    rep = ents[pds[2][0]][1]
    solid = ents[rep[3][0]][1]
    prof = ents[solid[0]][1]
    xd, yd = prof[3], prof[4]
    px, py = ents[ents[prof[2]][1][0]][1][0][:2]
    Rs, ts = axis_mat(ents, solid[1])
    depth = solid[3]
    pts = []
    for sx in (-xd / 2, xd / 2):
        for sy in (-yd / 2, yd / 2):
            for sz in (0.0, depth):
                p = Rs @ np.array([sx + px, sy + py, sz]) + ts
                pts.append(R @ p + t)
    pts = np.array(pts) * k
    return pts.min(axis=0), pts.max(axis=0)


def overlap_vol(b1, b2):
    d = np.minimum(b1[1], b2[1]) - np.maximum(b1[0], b2[0])
    return float(np.prod(np.clip(d, 0, None)))


def vol(b):
    return float(np.prod(b[1] - b[0]))


# ------------------------------------------------------------------ чтение модели
PREFIX = {"MILLI": 0.001, "CENTI": 0.01, "DECI": 0.1, None: 1.0}


def read_model(path):
    text = open(path, encoding="utf-8").read()
    ents = read_entities(text)
    byt = defaultdict(list)
    for i, (t, a) in ents.items(): byt[t].append(i)

    k = 1.0
    for i in byt["IFCSIUNIT"]:
        a = ents[i][1]
        if str(a[1]) == "LENGTHUNIT":
            k = PREFIX[str(a[2]) if a[2] is not None else None]

    cache = {}
    storeys = {}
    for i in byt["IFCBUILDINGSTOREY"]:
        a = ents[i][1]
        storeys[i] = {"name": a[2], "elev": a[9] * k}

    def val(v):
        x = v.val if isinstance(v, Typed) else v
        if isinstance(x, Enum) and str(x) in ("T", "F"):
            return str(x) == "T"
        return x

    psets = defaultdict(dict)            # элемент -> {pset: {prop: value}}
    qtos = defaultdict(dict)
    material = {}
    contained = {}
    voids = defaultdict(list)            # стена -> [проём]
    fills = {}                           # проём -> заполнение
    for i in byt["IFCRELDEFINESBYPROPERTIES"]:
        a = ents[i][1]; d = ents[a[5]]
        if d[0] == "IFCPROPERTYSET":
            props = {ents[p][1][0]: val(ents[p][1][2]) for p in d[1][4]}
            for o in a[4]: psets[o][d[1][2]] = props
        elif d[0] == "IFCELEMENTQUANTITY":
            qs = {ents[q][1][0]: ents[q][1][3] for q in d[1][5]}
            for o in a[4]: qtos[o][d[1][2]] = qs
    for i in byt["IFCRELASSOCIATESMATERIAL"]:
        a = ents[i][1]
        for o in a[4]: material[o] = ents[a[5]][1][0]
    for i in byt["IFCRELCONTAINEDINSPATIALSTRUCTURE"]:
        a = ents[i][1]
        for o in a[4]: contained[o] = a[5]
    for i in byt["IFCRELVOIDSELEMENT"]:
        a = ents[i][1]; voids[a[4]].append(a[5])
    for i in byt["IFCRELFILLSELEMENT"]:
        a = ents[i][1]; fills[a[4]] = a[5]

    elems = {}
    for cls in ("IFCWALL", "IFCSLAB", "IFCCOLUMN", "IFCDOOR", "IFCWINDOW", "IFCOPENINGELEMENT"):
        for i in byt[cls]:
            a = ents[i][1]
            b = element_box(ents, i, k, cache)
            e = {"ref": i, "cls": cls, "guid": a[0], "name": a[2], "box": b,
                 "material": material.get(i), "psets": psets.get(i, {}), "qto": qtos.get(i, {}),
                 "storey_decl": contained.get(i), "predef": str(a[8]) if cls in ("IFCWALL", "IFCSLAB", "IFCCOLUMN", "IFCOPENINGELEMENT") else None}
            if cls in ("IFCDOOR", "IFCWINDOW"):
                e["h"], e["w"] = a[8] * k, a[9] * k
            elems[i] = e
    return {"k": k, "storeys": storeys, "elems": elems, "voids": voids, "fills": fills}


# ------------------------------------------------------------------ анализ
def storey_of_box(m, box):
    zmid = (box[0][2] + box[1][2]) / 2
    best = None
    for sid, s in m["storeys"].items():
        if s["elev"] - 0.2 <= zmid <= s["elev"] + 2.8 + 1e-9:
            best = sid
    return best


def analyse(m):
    E = m["elems"]
    res = {}
    # чистый объём
    for i, e in E.items():
        if e["cls"] in ("IFCWALL", "IFCSLAB", "IFCCOLUMN"):
            v = vol(e["box"])
            for o in m["voids"].get(i, []):
                v -= overlap_vol(e["box"], E[o]["box"])
            e["net"] = v
    structural = [i for i, e in E.items() if e["cls"] in ("IFCWALL", "IFCSLAB", "IFCCOLUMN")]

    viol = {k: [] for k in ("R1", "R2", "R3a", "R3b", "R4", "R5", "R6", "R7", "R8")}
    for i in structural:
        e = E[i]
        if e["material"] is None: viol["R1"].append(e["guid"])
        q = None
        for qs in e["qto"].values():
            if "NetVolume" in qs: q = qs["NetVolume"]
        if q is not None and abs(q - e["net"]) > 0.02 * e["net"]: viol["R2"].append(e["guid"])
    for i, e in E.items():
        if e["cls"] == "IFCDOOR":
            fe = e["psets"].get("Pset_DoorCommon", {}).get("FireExit")
            if fe is True and e["w"] < 1.0 - 1e-9: viol["R3a"].append(e["guid"])
            if e["w"] < 0.8 - 1e-9: viol["R3b"].append(e["guid"])
        if e["cls"] == "IFCWALL":
            ps = e["psets"].get("Pset_WallCommon", {})
            if ps.get("IsExternal") is True and not ps.get("FireRating"): viol["R4"].append(e["guid"])
    # дубликаты
    seen = {}
    dups = []
    for i in structural:
        e = E[i]
        key = (e["cls"], tuple(np.round(e["box"][0], 3)), tuple(np.round(e["box"][1], 3)))
        if key in seen: dups.append(i)
        else: seen[key] = i
    viol["R5"] = [E[i]["guid"] for i in dups]
    # этаж
    for i in structural:
        e = E[i]
        gs = storey_of_box(m, e["box"])
        if gs is not None and e["storey_decl"] != gs: viol["R6"].append(e["guid"])
    # колонны против стен
    walls = [i for i in structural if E[i]["cls"] == "IFCWALL" and i not in dups]
    for i in structural:
        e = E[i]
        if e["cls"] != "IFCCOLUMN": continue
        if any(overlap_vol(e["box"], E[w]["box"]) > 1e-6 for w in walls):
            viol["R7"].append(e["guid"])
    # проёмы в стенах
    for i, e in E.items():
        if e["cls"] != "IFCOPENINGELEMENT": continue
        host = [w for w, ops in m["voids"].items() if i in ops]
        if host and E[host[0]]["cls"] == "IFCWALL" and i not in m["fills"]:
            viol["R8"].append(e["guid"])
    for k in viol: viol[k] = sorted(viol[k])

    inv = defaultdict(int)
    for i, e in E.items():
        if e["cls"] == "IFCOPENINGELEMENT": continue
        s = m["storeys"][storey_of_box(m, e["box"]) or e["storey_decl"]]["name"]
        inv[f"{e['cls']}|{s}"] += 1
    res["inventory_by_geometric_storey"] = dict(sorted(inv.items()))
    res["violations"] = viol
    res["_dups"] = dups
    return res


# ------------------------------------------------------------------ смета и график (общие формулы)
KG = {"slab": 110.0, "wall": 80.0, "column": 180.0}
PRICE_REBAR, PRICE_WIN, PRICE_DOOR, PRICE_EXIT = 78.0, 18000.0, 12000.0, 26000.0
DEFAULT_MAT = {"IFCCOLUMN": "Concrete B30", "IFCSLAB": "Concrete B25", "IFCWALL": "Concrete B25"}
PRICE_M3 = {"Concrete B25": 5200.0, "Concrete B30": 5900.0, "Кирпич М100": 7800.0}
PUMP, REBAR_DAY, BRICK_DAY = 60.0, 1200.0, 15.0
FORMW, CURE_SLAB, CURE_CW = 3, 7, 3


def estimate_and_schedule(items, doors_windows):
    """items: список dict(cls, storey 'L1..L4/Roof', material or None, interior bool, net). doors_windows: (n_win, n_door, n_exit)."""
    cost = 0.0
    per = defaultdict(lambda: defaultdict(float))
    for it in items:
        mat = it["material"] or DEFAULT_MAT[it["cls"]]
        v = it["net"]
        cost += v * PRICE_M3[mat]
        brick = mat.startswith("Кирпич")
        if not brick:
            kind = {"IFCSLAB": "slab", "IFCWALL": "wall", "IFCCOLUMN": "column"}[it["cls"]]
            kg = v * KG[kind]
            cost += kg * PRICE_REBAR
            grp = "slab" if kind == "slab" else "cw"
            per[it["storey"]][grp + "_v"] += v; per[it["storey"]][grp + "_kg"] += kg
        else:
            per[it["storey"]]["brick_v"] += v
    nw, nd, ne = doors_windows
    cost += nw * PRICE_WIN + (nd - ne) * PRICE_DOOR + ne * PRICE_EXIT

    t = 0
    ends = {}
    for s in ["L1", "L2", "L3", "L4"]:
        d = per[s]
        t += FORMW
        t += math.ceil(d["slab_kg"] / REBAR_DAY)
        t += math.ceil(d["slab_v"] / PUMP)
        t += CURE_SLAB
        t += math.ceil(d["cw_kg"] / REBAR_DAY)
        t += math.ceil(d["cw_v"] / PUMP)
        t += CURE_CW
        ends[s] = t
        ends[s + "_brick"] = t + math.ceil(d["brick_v"] / BRICK_DAY)
    d = per["Roof"]
    t += FORMW + math.ceil(d["slab_kg"] / REBAR_DAY) + math.ceil(d["slab_v"] / PUMP) + CURE_SLAB
    total = max(t, ends["L4_brick"])
    return {"cost_rub": round(cost, 2),
            "per_storey": {s: {k: round(v, 3) for k, v in per[s].items()} for s in per},
            "total_days": total, "frame_end": t, "brick4_end": ends["L4_brick"]}


def reference_solution(path):
    m = read_model(path)
    a = analyse(m)
    E = m["elems"]
    items = []
    for i, e in E.items():
        if e["cls"] in ("IFCWALL", "IFCSLAB", "IFCCOLUMN") and i not in a["_dups"]:
            sid = storey_of_box(m, e["box"])
            name = m["storeys"][sid]["name"] if sid is not None else None
            if name is None:
                name = "Roof" if e["box"][0][2] > 11.5 else "?"
            items.append({"cls": e["cls"], "storey": name, "material": e["material"], "net": e["net"]})
    nw = sum(1 for e in E.values() if e["cls"] == "IFCWINDOW")
    doors = [e for e in E.values() if e["cls"] == "IFCDOOR"]
    ne = sum(1 for e in doors if e["psets"].get("Pset_DoorCommon", {}).get("FireExit") is True)
    out = estimate_and_schedule(items, (nw, len(doors), ne))
    out["violations"] = a["violations"]
    out["inventory_by_geometric_storey"] = a["inventory_by_geometric_storey"]
    out["length_unit_to_m"] = m["k"]
    return out


if __name__ == "__main__":
    import json, sys
    print(json.dumps(reference_solution(sys.argv[1]), ensure_ascii=False, indent=1))
