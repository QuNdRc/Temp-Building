"""Пайплайн данных: чтение CSV/JSON -> чистка -> агрегаты -> аномалии -> CSV + график.

Запуск:
    python pipeline.py data.csv
    python pipeline.py data.json

Подходит для кейсов: заявки, дефекты, графики производства работ, сметы,
ведомости объёмов. Читает любой CSV/JSON, определяет числовые колонки,
считает по ним агрегаты, находит аномалии (метод 3 сигм) и строит
гистограммы/боксплоты для отчёта на защите.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import sys
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")  # без окна, только сохранение в файл
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def read_table(path: str) -> pd.DataFrame:
    """Читает CSV или JSON в pandas-таблицу. JSON может быть списком записей
    или словарём вида {"data": [...]}. Вложенные объекты разворачиваются."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            # ищем первый список значений — это обычно и есть данные
            for v in raw.values():
                if isinstance(v, list):
                    raw = v
                    break
        return pd.json_normalize(raw)
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Минимальная чистка: убираем полностью пустые колонки, заполняем
    пропуски в числовых колонках медианой."""
    df = df.dropna(axis=1, how="all").copy()
    num = df.select_dtypes(include=[np.number]).columns
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df[c] = df[c].fillna(df[c].median())
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Сводная таблица агрегатов по числовым колонкам."""
    num = df.select_dtypes(include=[np.number])
    agg = num.agg(["count", "mean", "std", "min", "max"]).T
    agg.columns = ["count", "mean", "std", "min", "max"]
    return agg


def anomalies(df: pd.DataFrame, k: float = 3.0) -> pd.DataFrame:
    """Аномалии по правилу |x - mean| > k * std для каждой числовой колонки."""
    num = df.select_dtypes(include=[np.number])
    rows = []
    for c in num.columns:
        mean, std = num[c].mean(), num[c].std()
        if std == 0 or pd.isna(std):
            continue
        mask = (num[c] - mean).abs() > k * std
        for idx in np.flatnonzero(mask):
            rows.append({"column": c, "row": int(idx), "value": float(num[c].iloc[idx]),
                         "mean": float(mean), "std": float(std)})
    return pd.DataFrame(rows)


def plot(df: pd.DataFrame, out: str) -> None:
    """Гистограммы числовых колонок + общий боксплот — картинка для защиты."""
    num = df.select_dtypes(include=[np.number])
    if num.empty:
        return
    n = len(num.columns)
    fig, axes = plt.subplots(n, 1, figsize=(8, 2.5 * n), squeeze=False)
    for ax, (c, _) in zip(axes[:, 0], num.items()):
        ax.hist(num[c].dropna(), bins=30, alpha=0.7, color="#2c7bb6")
        ax.set_title(c)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="CSV/JSON -> таблица -> агрегаты -> CSV")
    ap.add_argument("input", help="путь к .csv или .json")
    ap.add_argument("--out", default="out", help="префикс выходных файлов")
    args = ap.parse_args()

    df = read_table(args.input)
    df = clean(df)

    agg = aggregate(df)
    anom = anomalies(df)

    print(f"строк: {len(df)}, колонок: {len(df.columns)}")
    print("\nАгрегаты по числовым колонкам:\n", agg.to_string())
    print(f"\nАномалий найдено: {len(anom)}")
    if not anom.empty:
        print(anom.to_string())

    agg.to_csv(f"{args.out}_agg.csv", index=True)
    anom.to_csv(f"{args.out}_anomalies.csv", index=False)
    df.to_csv(f"{args.out}_clean.csv", index=False)
    plot(df, f"{args.out}_hist.png")

    print(f"\nВыгружено: {args.out}_agg.csv, {args.out}_anomalies.csv, "
          f"{args.out}_clean.csv, {args.out}_hist.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
