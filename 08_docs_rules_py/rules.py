"""Разбор документов через LLM -> поля JSON -> проверка по правилам -> отчёт.

Запуск (без LLM, на готовом JSON):
    python rules.py sample_act.json

Запуск (с LLM, сам вытащит поля из текста):
    python rules.py --text "Акт № 127 ..." --host http://127.0.0.1:8080

Идея: LLM превращает акт/документ в структурированные поля, дальше код
проверяет эти поля по заранее заданным правилам (нормы, лимиты, сроки).
LLM только читает, решения принимает код — это надёжнее на защите.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---- Правила проверки (подставь свои нормы) ----
def check_rules(doc: dict) -> list[dict]:
    """Возвращает список нарушений. Пустой список = документ в порядке."""
    issues: list[dict] = []

    # срок выполнения не должен превышать нормативный
    if "duration_days" in doc and doc.get("duration_days", 0) > 30:
        issues.append({
            "rule": "срок работ > 30 дней",
            "field": "duration_days",
            "value": doc["duration_days"],
            "message": "требуется обоснование или разбивка на этапы",
        })

    # сумма контракта не должна превышать лимит без доп. согласования
    if "amount" in doc and doc.get("amount", 0) > 5_000_000:
        issues.append({
            "rule": "сумма > 5 млн руб.",
            "field": "amount",
            "value": doc["amount"],
            "message": "нужно согласование руководства",
        })

    # список дефектов не должен быть пустым для акта освидетельствования
    if "defects" in doc:
        defects = doc["defects"]
        if not isinstance(defects, list) or len(defects) == 0:
            issues.append({
                "rule": "дефекты не заполнены",
                "field": "defects",
                "value": defects,
                "message": "акт должен содержать список дефектов",
            })
        elif any(not d or str(d).strip() == "" for d in defects):
            issues.append({
                "rule": "пустой дефект в списке",
                "field": "defects",
                "value": defects,
                "message": "в списке есть пустая запись",
            })

    return issues


def report(doc: dict, issues: list[dict]) -> str:
    lines = ["=== Проверка документа ===", f"Поля: {json.dumps(doc, ensure_ascii=False)}"]
    if not issues:
        lines.append("Нарушений не найдено.")
    else:
        lines.append(f"Нарушений: {len(issues)}")
        for i, it in enumerate(issues, 1):
            lines.append(f"  [{i}] {it['rule']}: {it['message']} (значение: {it['value']})")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM-разбор + проверка по правилам")
    ap.add_argument("json_file", nargs="?", help="готовый JSON с полями документа")
    ap.add_argument("--text", help="сырой текст документа (тогда используется LLM)")
    ap.add_argument("--host", default="http://127.0.0.1:8080")
    args = ap.parse_args()

    if args.text:
        # подключаем LLM-модуль из соседней заготовки
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "04_llm_json_py"))
        from llm import llm_json, SYSTEM_JSON

        prompt = (
            "Извлеки из текста документа поля: number, date, object, contractor, "
            "amount (число в рублях), duration_days (число), defects (список строк). "
            "Если поля нет — поставь null. Текст: " + args.text
        )
        doc = llm_json(args.host, prompt, SYSTEM_JSON)
    elif args.json_file:
        doc = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    else:
        ap.error("нужен либо json_file, либо --text")

    issues = check_rules(doc)
    print(report(doc, issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
