"""Мини-генератор пояснительной записки (ПЗ) в Word.

Универсальный модуль: любой кейс складывает свои результаты в структуру
Report и получает готовый .docx с заголовками, таблицами и картинками.

Запуск (демо):  python report.py
Использование в кейсе:
    from report import Report
    rep = Report("Кейс 2 «Бытовой городок»")
    rep.section("Часть 1. План")
    rep.paragraph("текст")
    rep.table(headers, rows)
    rep.image("plan_solution.png", "Подпись")
    rep.save("case2_otchet.docx")

Зависимости: python-docx.
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DARK = RGBColor(0x1F, 0x3B, 0x63)  # тёмно-синий для заголовков


class Report:
    def __init__(self, title: str, subtitle: str = ""):
        self.doc = Document()
        # титульный заголовок
        h = self.doc.add_heading(title, level=0)
        for run in h.runs:
            run.font.color.rgb = DARK
        if subtitle:
            p = self.doc.add_paragraph(subtitle)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.italic = True
                run.font.size = Pt(11)

    def section(self, text: str) -> None:
        h = self.doc.add_heading(text, level=1)
        for run in h.runs:
            run.font.color.rgb = DARK

    def subsection(self, text: str) -> None:
        self.doc.add_heading(text, level=2)

    def paragraph(self, text: str, bold: bool = False) -> None:
        p = self.doc.add_paragraph()
        run = p.add_run(text)
        run.bold = bold

    def bullet(self, text: str) -> None:
        self.doc.add_paragraph(text, style="List Bullet")

    def table(self, headers: list[str], rows: list[list]) -> None:
        """Таблица с шапкой. rows — список строк (каждая строка — список ячеек)."""
        t = self.doc.add_table(rows=1, cols=len(headers))
        t.style = "Light Grid Accent 1"
        hdr = t.rows[0].cells
        for i, htext in enumerate(headers):
            hdr[i].text = str(htext)
            for p in hdr[i].paragraphs:
                for run in p.runs:
                    run.bold = True
        for row in rows:
            cells = t.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = str(val)

    def image(self, path: str, caption: str = "", width_in: float = 6.0) -> None:
        if not Path(path).exists():
            self.paragraph(f"[картинка не найдена: {path}]")
            return
        self.doc.add_picture(str(path), width=Inches(width_in))
        if caption:
            cap = self.doc.add_paragraph(caption)
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in cap.runs:
                run.italic = True
                run.font.size = Pt(9)

    def save(self, path: str) -> None:
        self.doc.save(path)
        print(f"ПЗ сохранена: {path}")


def demo() -> None:
    rep = Report("Демо-отчёт", "пример использования генератора ПЗ")
    rep.section("Часть 1. Данные")
    rep.paragraph("Краткое описание результатов.", bold=True)
    rep.table(["Параметр", "Значение"], [["Площадь", "288 м²"], ["Срок", "51 день"]])
    rep.section("Часть 2. Иллюстрация")
    rep.image("demo.png", "Рис. 1 — план")
    rep.save("demo_report.docx")


if __name__ == "__main__":
    demo()
