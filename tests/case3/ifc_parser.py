"""Ручной парсер IFC4 (STEP) для кейса 3.

Разбирает #id=ENTITY(args) с вложенными скобками, строками в кавычках,
экранированием \X2\...\X0\ и перечислениями .VALUE.

Ядро — parse(), который возвращает dict id -> (entity, args), где args —
рекурсивная структура: списки, строки, числа, перечисления, ссылки #id.

Запуск: python ifc_parser.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
IFC_FILE = HERE / "case3_model.ifc"


def unescape_utf(s: str) -> str:
    """Раскрывает \X2\HHHH\X0\ — UTF-16 code units в кириллицу."""
    def repl(m):
        hexs = m.group(1)
        units = [int(hexs[i:i + 4], 16) for i in range(0, len(hexs), 4)]
        try:
            return bytes([u for u in units if u < 256]).decode("utf-8", errors="replace")
        except Exception:
            return m.group(0)
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", repl, s)


class Token:
    __slots__ = ("kind", "value")
    def __init__(self, kind, value):
        self.kind = kind  # 'ref','str','num','enum','lparen','rparen','comma','dollar'
        self.value = value


def tokenize(line: str):
    """Токенизирует содержимое ENTITY(...) без внешних скобок."""
    tokens = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            tokens.append(Token("lparen", "(")); i += 1
        elif c == ")":
            tokens.append(Token("rparen", ")")); i += 1
        elif c == ",":
            tokens.append(Token("comma", ",")); i += 1
        elif c == "$":
            tokens.append(Token("dollar", "$")); i += 1
        elif c == "#":
            j = i + 1
            while j < n and line[j].isdigit():
                j += 1
            tokens.append(Token("ref", line[i:j])); i = j
        elif c == "'":
            j = i + 1
            buf = []
            while j < n:
                if line[j] == "'" and j + 1 < n and line[j + 1] == "'":
                    buf.append("'"); j += 2
                elif line[j] == "'":
                    break
                else:
                    buf.append(line[j]); j += 1
            tokens.append(Token("str", "".join(buf))); i = j + 1
        elif c == ".":
            j = i + 1
            while j < n and line[j] not in ".,)":
                j += 1
            tokens.append(Token("enum", line[i + 1:j])); i = j
        else:
            # число или другой токен
            j = i
            while j < n and line[j] not in ",()$":
                j += 1
            val = line[i:j].strip()
            if val:
                tokens.append(Token("num", val))
            i = j
    return tokens


class P:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def parse_value(self):
        tok = self.peek()
        if tok is None:
            return None
        if tok.kind == "lparen":
            return self.parse_list()
        if tok.kind == "ref":
            self.next()
            return {"$ref": tok.value}
        if tok.kind == "str":
            self.next()
            return tok.value
        if tok.kind == "num":
            self.next()
            s = tok.value
            if s in ("*",):
                return None
            try:
                return int(s)
            except ValueError:
                try:
                    return float(s)
                except ValueError:
                    return s
        if tok.kind == "enum":
            self.next()
            return {"$enum": tok.value}
        if tok.kind == "dollar":
            self.next()
            return None
        if tok.kind == "comma":
            return None
        raise ValueError(f"неожиданный токен: {tok.kind} {tok.value}")

    def parse_list(self):
        self.next()  # lparen
        items = []
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok.kind == "rparen":
                self.next()
                break
            if tok.kind == "comma":
                self.next()
                continue
            items.append(self.parse_value())
        return items


def parse_entity(line: str):
    """Строка '#id=ENTITY(args);' -> (id, entity, args)."""
    line = line.strip()
    if not line or line == "DATA" or line.startswith("END"):
        return None
    m = re.match(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)\s*;?\s*$", line, re.DOTALL)
    if not m:
        return None
    eid = int(m.group(1))
    entity = m.group(2)
    body = m.group(3)
    tokens = tokenize(body)
    p = P(tokens)
    args = []
    while p.peek() is not None:
        tok = p.peek()
        if tok.kind == "comma":
            p.next()
            continue
        args.append(p.parse_value())
    return eid, entity, args


def parse_file(path: Path) -> dict:
    """Возвращает {id: (entity, args)}."""
    data = path.read_text(encoding="utf-8", errors="replace")
    # IFC STEP: одна сущность на строку (в этом файле — да)
    entities = {}
    in_data = False
    for raw in data.splitlines():
        raw = raw.strip().lstrip("\ufeff")
        if raw == "DATA;":
            in_data = True
            continue
        if not in_data:
            continue
        if raw.startswith("ENDSEC"):
            break
        if not raw.startswith("#"):
            continue
        res = parse_entity(raw)
        if res:
            eid, entity, args = res
            entities[eid] = (entity, args)
    return entities


def ref(v):
    """Возвращает id из ссылки {'$ref': '#12'} или None."""
    if isinstance(v, dict) and "$ref" in v:
        return int(v["$ref"][1:])
    return None


def strval(v):
    """Возвращает строку (для перечислений и строк)."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and "$enum" in v:
        return v["$enum"]
    return None


def main():
    entities = parse_file(IFC_FILE)
    print(f"Сущностей распарсено: {len(entities)}")
    # распределение по типам
    from collections import Counter
    c = Counter(e for e, _ in entities.values())
    for e, n in sorted(c.items()):
        print(f"  {e}: {n}")


if __name__ == "__main__":
    main()
