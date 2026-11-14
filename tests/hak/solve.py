"""Кейс 11. Концепция многофункционального жилого дома — ЕДИНАЯ версия.

Все артефакты (results.json, case11_otchet.docx, scheme.png) считаются из
этого файла одним запуском, чтобы цифры не разъезжались между картинкой,
чертежами и отчётом.

Базовая версия (согласована с выжимкой и чертежами команды):
  участок 100x30 = 3000 м2 (0.3 га); кЗ 35% -> застройка 1050 м2; 5 этажей;
  надземная общая 5250 м2; ПСН (офисы, 1 эт.) 620 м2; квартиры 3480 м2 (50 шт);
  МОП/тех 1150 м2; жители 3480/33 = 105; подземный паркинг 37 м/м, 1300 м2.

Все недостающие нормы — ДОПУЩЕНИЯ, подписаны в ASSUMPTIONS и в отчёте.
Запуск: python solve.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "10_report_docx_py"))
from report import Report  # noqa: E402

NORMS = json.loads((HERE / "norms.json").read_text(encoding="utf-8"))

# ================= ДОПУЩЕНИЯ (подписываем на защите) =================
ASSUMPTIONS = {
    "site": "участок 100x30 м = 3000 м2 (0.3 га); противоречие 0.25/0.3 принято 0.3",
    "kZ": 0.35,                        # коэффициент застройки для ЦАО (норма не дана)
    "floors": 5,
    "offices_m2": 620,                 # ПСН на 1 этаже (меньше пятна застройки из-за входов/МОП)
    "flats_area_m2": 3480,             # квартирография 630+1280+900+670
    "m2_per_person": 33.0,             # таблица 1, МКД
    "living_share_min": 0.45,          # условие
    "parking_per_flat": 0.6,           # машиномест на квартиру (норматив не дан)
    "parking_per_100m2_psn": 1.0,      # машиномест на 100 м2 ПСН (не дано)
    "parking_m2_per_place": 35.0,      # удельная площадь подземного места с проездами (обычно 30-35)
    "green_site_m2": 750,              # 25% участка; норма участка >=5% (150 м2) выполнена с запасом
    "sport_m2_per_person": 1.0,        # спортплощадки (норматив не дан в материалах)
    "cadastral_rub_per_m2": 250_000,   # кадастровая стоимость земли ЦАО (не дана)
    "smr_above_rub_m2": 200_000,       # СМР надземная, бизнес-класс с отделкой (не дано)
    "smr_below_rub_m2": 250_000,       # СМР подземная (паркинг с рампами) (не дано)
    "pir_rub_m2": 12_000,              # ПИР стадий П+РД (не дано)
    "expertise_pct_smr": 0.05,         # Госэкспертиза ~5% СМР (не дано)
    "market_living_rub_m2": 900_000,   # рынок: новостройки бизнес-класса ЦАО (Кропоткинская),
                                       # источник: публичные агрегаторы (Циан/Домклик), уточнить на защите
    "market_psn_rub_m2": 800_000,      # рынок ПСН ЦАО (то же допущение-источник)
    "market_parking_rub_place": 3_000_000,  # машиноместо в подземном паркинге ЦАО
}


def compute() -> dict:
    A = ASSUMPTIONS
    N = NORMS

    site = 3000.0
    built = site * A["kZ"]                       # 1050
    above = built * A["floors"]                  # 5250
    psn = A["offices_m2"]                        # 620
    flats_area = A["flats_area_m2"]              # 3480
    mop = above - psn - flats_area               # 1150
    residents = flats_area / A["m2_per_person"]  # 105.45
    res_r = round(residents)

    # доли жилой площади — показываем ОБЕ базы
    share_above = flats_area / above
    # паркинг
    fl = 50
    park_res = math.ceil(fl * A["parking_per_flat"])            # 30
    park_psn = math.ceil(psn / 100 * A["parking_per_100m2_psn"])  # 7
    park_places = park_res + park_psn                            # 37
    underground = math.ceil(park_places * A["parking_m2_per_place"] / 50) * 50  # 1300
    total_all = above + underground                              # 6550
    share_total = flats_area / total_all

    # квартирография
    rooms = [
        ("1-комн", 15, 42.0, 630),
        ("2-комн", 20, 64.0, 1280),
        ("3-комн", 10, 90.0, 900),
        ("4-комн", 5, 134.0, 670),
    ]

    # соцобъекты: потребность + площади по таблице 3
    school_places = math.ceil(res_r * N["table3"]["school"]["places_per_1000"] / 1000)
    doo_places = math.ceil(res_r * N["table3"]["preschool"]["places_per_1000"] / 1000)
    clinic_visits = res_r * N["table3"]["clinic"]["visits_per_shift_per_1000"]["mixed"] / 1000
    school_bld = school_places * 18      # <=550 мест -> 18 м2/место
    school_land = school_places * 19     # <=900 мест -> 19 м2/место
    doo_bld = doo_places * 27            # <=125 мест -> 27 м2/место
    doo_land = doo_places * 35           # <=150 мест -> 35 м2/место
    clinic_bld = clinic_visits * N["table3"]["clinic"]["floor_area_m2_per_visit_max"]
    clinic_land_ha = N["table3"]["clinic"]["land_ha_per_object"]

    # площадки и озеленение (округление ВВЕРХ — минимумы)
    play = math.ceil(N["table2_territories"]["playground_m2_per_person"] * res_r)   # 53
    rest = math.ceil(N["table2_territories"]["adult_rest_m2_per_person"] * res_r)   # 11
    sport = math.ceil(A["sport_m2_per_person"] * res_r)                             # 106 -> 105? ceil(105.45)=106
    green = A["green_site_m2"]                                                      # 750
    green_min_site = site * N["constraints"]["green_share_of_site_min"]             # 150

    # баланс территории
    paved = site - built - green - play - rest - sport

    # бюджет
    land = site * A["cadastral_rub_per_m2"]
    smr = above * A["smr_above_rub_m2"] + underground * A["smr_below_rub_m2"]
    pir = above * A["pir_rub_m2"]
    exp = smr * A["expertise_pct_smr"]
    total_cost = land + smr + pir + exp
    cost_per_living = total_cost / flats_area
    cost_per_total = total_cost / total_all
    cost_wo_land = smr + pir + exp
    cost_wo_land_per_living = cost_wo_land / flats_area

    # рынок и маржа (критерий 5)
    revenue = (flats_area * A["market_living_rub_m2"]
               + psn * A["market_psn_rub_m2"]
               + park_places * A["market_parking_rub_place"])
    margin = revenue - total_cost
    margin_pct = margin / revenue * 100

    return {
        "site_m2": site, "built_m2": built, "above_m2": above, "psn_m2": psn,
        "flats_area_m2": flats_area, "mop_m2": mop, "residents": res_r,
        "flats": fl, "rooms": rooms,
        "share_of_above": round(share_above, 3), "share_of_total": round(share_total, 3),
        "underground_m2": underground, "park_places": park_places,
        "park_res": park_res, "park_psn": park_psn,
        "total_all_m2": total_all,
        "school_places": school_places, "doo_places": doo_places,
        "clinic_visits": round(clinic_visits, 1),
        "school_bld": school_bld, "school_land": school_land,
        "doo_bld": doo_bld, "doo_land": doo_land,
        "clinic_bld": round(clinic_bld, 1), "clinic_land_ha": clinic_land_ha,
        "play_m2": play, "rest_m2": rest, "sport_m2": sport,
        "green_m2": green, "green_min_site_m2": green_min_site, "paved_m2": paved,
        "land_rub": land, "smr_rub": smr, "pir_rub": pir, "exp_rub": exp,
        "total_cost_rub": total_cost,
        "cost_per_living": round(cost_per_living), "cost_per_total": round(cost_per_total),
        "cost_wo_land_per_living": round(cost_wo_land_per_living),
        "revenue_rub": revenue, "margin_rub": margin, "margin_pct": round(margin_pct, 1),
    }


TIMELINE = [
    ("ПИР, стадия П", 0, 4),
    ("Государственная экспертиза", 4, 7),
    ("ПИР, стадия РД", 5, 10),
    ("Подготовительные работы", 7, 9),
    ("Подземная часть (паркинг)", 9, 13),
    ("Наземная часть, 5 этажей", 13, 25),
    ("Отделка и внутренние инженерные сети", 20, 28),
    ("Благоустройство и озеленение", 26, 29),
    ("Ввод в эксплуатацию, ЗОС", 29, 30),
]


def plot_scheme(r: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Wedge

    fig, ax = plt.subplots(figsize=(12, 5), dpi=130)
    W, H = 100.0, 30.0
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, edgecolor="black", lw=2))

    # озеленение по периметру: 2 полосы 100x3 + 2 торца 3x24 = 744 ~ 750 м2
    ax.add_patch(Rectangle((0, 0), W, 3, facecolor="#a5d6a7", edgecolor="#2e7d32", lw=0.8))
    ax.add_patch(Rectangle((0, H - 3), W, 3, facecolor="#a5d6a7", edgecolor="#2e7d32", lw=0.8))
    ax.add_patch(Rectangle((0, 3), 3, H - 6, facecolor="#a5d6a7", edgecolor="#2e7d32", lw=0.8))
    ax.add_patch(Rectangle((W - 3, 3), 3, H - 6, facecolor="#a5d6a7", edgecolor="#2e7d32", lw=0.8))
    # карман 2x3 = 6 м2: периметр 744 + карман = ровно 750 м2 (25%)
    ax.add_patch(Rectangle((87, 13), 2, 3, facecolor="#a5d6a7", edgecolor="#2e7d32", lw=0.8))

    # здание 70x15 = 1050 м2
    bx, by, bw, bh = 15, 7.5, 70, 15
    ax.add_patch(Rectangle((bx, by), bw, bh, facecolor="#bdbdbd", edgecolor="black", lw=1.5))
    ax.text(bx + bw / 2, by + bh / 2 + 1.5, "Жилой дом, 5 эт.", ha="center", fontsize=9)
    ax.text(bx + bw / 2, by + bh / 2, f"застройка {r['built_m2']:.0f} м2 (35%)", ha="center", fontsize=8)
    ax.text(bx + bw / 2, by + bh / 2 - 1.8, f"ПСН 1 эт. {r['psn_m2']:.0f} м2", ha="center", fontsize=8, color="#37474f")
    # подземный паркинг штрихом под зданием
    ax.add_patch(Rectangle((bx - 2, by - 2), bw + 4, bh + 4, fill=False,
                           edgecolor="#1565c0", lw=1.2, linestyle="--"))
    ax.text(bx + bw / 2, by - 3.2, f"подземный паркинг {r['park_places']} м/м, {r['underground_m2']:.0f} м2",
            ha="center", fontsize=8, color="#1565c0")

    # площадки во дворе (восточная часть)
    ax.add_patch(Rectangle((87, 6), 8, 7, facecolor="#ffe082", edgecolor="#f9a825"))
    ax.text(91, 9.5, f"детская\n{r['play_m2']} м2", ha="center", fontsize=7)
    ax.add_patch(Rectangle((87, 16), 10, 10, facecolor="#90caf9", edgecolor="#1565c0"))
    ax.text(92, 21, f"спорт\n{r['sport_m2']} м2", ha="center", fontsize=7)
    ax.add_patch(Rectangle((5, 6), 6, 3, facecolor="#ce93d8", edgecolor="#6a1b9a"))
    ax.text(8, 4.6, f"отдых {r['rest_m2']} м2", ha="center", fontsize=7)

    # инсоляция: солнце с юга
    ax.add_patch(Wedge((50, -9), 6, 60, 120, facecolor="#fff59d", edgecolor="#f57f17"))
    ax.text(50, -11.5, "инсоляция: южный фасад, >= 2.5 ч/сут (СанПиН 1.2.3685-21)",
            ha="center", fontsize=8, color="#f57f17")
    # север
    ax.annotate("С", xy=(2, 33), fontsize=10, fontweight="bold")
    ax.annotate("", xy=(2, 32), xytext=(2, 28),
                arrowprops=dict(arrowstyle="->", lw=1.5))

    ax.set_xlim(-6, W + 6)
    ax.set_ylim(-14, H + 6)
    ax.set_aspect("equal")
    ax.set_title("Схема размещения зон, инсоляции и паркинга (участок 100x30 м)", fontsize=12)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def make_report(r: dict, path_png: Path) -> None:
    A = ASSUMPTIONS
    rep = Report("Кейс 11. Концепция многофункционального жилого дома",
                 "Единая версия расчёта: ТЭП, соцобъекты, паркинг, бюджет, сроки")

    rep.section("1. ТЭП")
    rep.table(["Показатель", "Значение"],
              [["Участок", f"{r['site_m2']:.0f} м2 (100x30 м, 0.3 га)"],
               ["Площадь застройки (кЗ 35%)", f"{r['built_m2']:.0f} м2"],
               ["Надземная общая (5 эт.)", f"{r['above_m2']:.0f} м2"],
               ["ПСН (офисы, 1 эт.)", f"{r['psn_m2']:.0f} м2"],
               ["Площадь квартир", f"{r['flats_area_m2']:.0f} м2"],
               ["МОП / техпомещения", f"{r['mop_m2']:.0f} м2"],
               ["Подземная часть (паркинг)", f"{r['underground_m2']:.0f} м2"],
               ["Общая площадь (надзем+подзем)", f"{r['total_all_m2']:.0f} м2"],
               ["Жителей", f"{r['residents']} (3480/33 м2)"],
               ["Квартир", f"{r['flats']} шт"],
               ["Доля жилой от надземной", f"{r['share_of_above']*100:.1f}% (норма >= 45%)"],
               ["Доля жилой от общей с паркингом", f"{r['share_of_total']*100:.1f}% (тоже >= 45%)"]])
    rep.table(["Тип", "Шт", "Средняя площадь, м2", "Сумма, м2"],
              [[n, c, s, a] for n, c, s, a in r["rooms"]])

    rep.section("2. Социальные объекты (потребность и площади по таблице 3)")
    rep.table(["Объект", "Потребность", "Здание, м2", "Участок, м2"],
              [["Школа", f"{r['school_places']} мест (90/1000 жит)", r["school_bld"], r["school_land"]],
               ["ДОО (детсад)", f"{r['doo_places']} мест (44/1000 жит)", r["doo_bld"], r["doo_land"]],
               ["Поликлиника (смешанная)", f"{r['clinic_visits']} пос/смену (19/1000)", r["clinic_bld"], f"{r['clinic_land_ha']} га"],
               ["Детские площадки", f"{r['play_m2']} м2 (0.5 м2/чел, округл. вверх)", "-", "в балансе участка"],
               ["Отдых взрослых", f"{r['rest_m2']} м2 (0.1 м2/чел, округл. вверх)", "-", "в балансе участка"],
               ["Спортплощадки", f"{r['sport_m2']} м2 (1.0 м2/чел, допущение)", "-", "в балансе участка"]])
    rep.paragraph("Потребность мала (105 жителей): на участке соцобъекты не размещаются — "
                  "покрываются существующей сетью ЦАО (плотная застройка). Компенсационные мероприятия: "
                  "целевые отчисления на реконструкцию соседних школы/ДОО.")

    rep.section("3. Озеленение и баланс территории")
    rep.table(["Зона", "м2"],
              [["Застройка", r["built_m2"]], ["Озеленение (25% участка; норма участка >= 5% = 150 м2)", r["green_m2"]],
               ["Детская площадка", r["play_m2"]], ["Отдых взрослых", r["rest_m2"]],
               ["Спортплощадки", r["sport_m2"]], ["Проезды, пожарный проезд, твёрдые покрытия", r["paved_m2"]],
               ["ИТОГО", r["site_m2"]]])

    rep.section("4. Подземный паркинг")
    rep.paragraph(f"Жилые места: {r['flats']} кв x 0.6 = {r['park_res']}; ПСН: {r['psn_m2']:.0f}/100 = {r['park_psn']}; "
                  f"итого {r['park_places']} м/м x 35 м2 = {r['underground_m2']:.0f} м2 подземной части. "
                  "Все парковки подземные (условие).")

    rep.section("5. Бюджет строительства")
    rep.table(["Статья", "руб"],
              [["Покупка участка (кадастровая, 250 тыс/м2)", f"{r['land_rub']:,.0f}".replace(",", " ")],
               ["СМР (надзем 200 тыс/м2 + подзем 250 тыс/м2)", f"{r['smr_rub']:,.0f}".replace(",", " ")],
               ["ПИР (12 тыс/м2)", f"{r['pir_rub']:,.0f}".replace(",", " ")],
               ["Госэкспертиза (5% СМР)", f"{r['exp_rub']:,.0f}".replace(",", " ")],
               ["ИТОГО", f"{r['total_cost_rub']:,.0f}".replace(",", " ")]])
    rep.paragraph(f"Удельная стоимость: {r['cost_per_living']:,} руб/м2 жилой; "
                  f"{r['cost_per_total']:,} руб/м2 общей; без земли {r['cost_wo_land_per_living']:,} руб/м2 жилой."
                  .replace(",", " "), bold=True)

    rep.section("6. Рыночная стоимость и маржа (критерий 5)")
    rep.paragraph(f"Выручка: квартиры 3480 м2 x 900 тыс + ПСН 620 x 800 тыс + {r['park_places']} м/м x 3 млн = "
                  f"{r['revenue_rub']/1e9:.2f} млрд руб. Маржа {r['margin_rub']/1e9:.2f} млрд ({r['margin_pct']}%). "
                  "Источник цены: публичные агрегаторы (Циан/Домклик), бизнес-класс ЦАО — допущение, уточнить на защите.")

    rep.section("7. Срок реализации (по этапам)")
    rep.table(["Этап", "Начало, мес", "Окончание, мес"], [[n, a, b] for n, a, b in TIMELINE])
    rep.paragraph("Итого 30 месяцев до ввода.", bold=True)

    rep.section("8. Инсоляция")
    rep.paragraph("Дом вытянут по оси запад-восток, фасады юг/север. Все квартиры двухсторонние или угловые: "
                  "норматив >= 2.5 ч/сут (СанПиН 1.2.3685-21) обеспечивается южной и восточно-западной ориентацией. "
                  "Северными остаются только МОП и лестницы. Схема — на рис. 1.")

    rep.section("Принятые допущения")
    for k, v in A.items():
        rep.bullet(f"{k} = {v}")

    rep.section("Приложение")
    rep.image(str(path_png), "Рис. 1 — схема размещения зон, инсоляции и паркинга", width_in=6.4)
    rep.save(str(HERE / "case11_otchet.docx"))


def main() -> None:
    r = compute()
    print("=== Единая версия (участок 0.3 га, 100x30) ===")
    for k, v in r.items():
        if k != "rooms":
            print(f"  {k}: {v}")
    print("  rooms:", [(n, c, s, a) for n, c, s, a in r["rooms"]])

    plot_scheme(r, HERE / "scheme.png")
    make_report(r, HERE / "scheme.png")

    result = {"assumptions": ASSUMPTIONS, "tep_and_budget": r,
              "timeline": [{"stage": n, "start": a, "end": b} for n, a, b in TIMELINE],
              "note": "Единая версия: все цифры согласованы с выжимкой и чертежами; "
                      "противоречие участка 0.25/0.3 принято 0.3 га."}
    (HERE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print("\nscheme.png, case11_otchet.docx, results.json сохранены")


if __name__ == "__main__":
    main()
