"""Единая точка входа в проект-арсенал для строительного хакатона.

Команды:
    python run.py                  — список шаблонов и кейсов
    python run.py run <name>       — запустить шаблон или кейс
    python run.py new <caseX>      — создать каркас нового кейса в tests/

Примеры:
    python run.py run 02_cpm_monte_carlo
    python run.py run case2
    python run.py new case4
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent

# Шаблоны: name -> (папка, файл запуска, язык)
TEMPLATES = {
    "01_optimization_cpp": ("01_optimization_cpp", "main.cpp", "cpp"),
    "02_cpm_monte_carlo": ("02_cpm_monte_carlo", "main.cpp", "cpp"),
    "03_data_pipeline_py": ("03_data_pipeline_py", "pipeline.py", "py"),
    "04_llm_json_py": ("04_llm_json_py", "llm.py", "py"),
    "05_geometry_py": ("05_geometry_py", "geometry.py", "py"),
    "06_computer_vision_py": ("06_computer_vision_py", "vision.py", "py"),
    "07_calcs_cpp": ("07_calcs_cpp", "main.cpp", "cpp"),
    "08_docs_rules_py": ("08_docs_rules_py", "rules.py", "py"),
    "09_assignment_cpp": ("09_assignment_cpp", "main.cpp", "cpp"),
    "10_report_docx_py": ("10_report_docx_py", "report.py", "py"),
}

CPP_SOLUTIONS = {
    "01_optimization_cpp": "optimize",
    "02_cpm_monte_carlo": "cpm",
    "07_calcs_cpp": "calcs",
    "09_assignment_cpp": "assignment",
}


def list_cases() -> list[str]:
    tests = HERE / "tests"
    if not tests.exists():
        return []
    return sorted(d.name for d in tests.iterdir() if d.is_dir() and d.name.startswith("case"))


def run_template(name: str, args: list[str]) -> int:
    folder, entry, lang = TEMPLATES[name]
    target = HERE / folder / entry
    if lang == "py":
        return subprocess.call([sys.executable, str(target), *args])
    # C++: компилируем MSVC, если доступен
    exe = CPP_SOLUTIONS.get(name, "main")
    exe_path = HERE / folder / f"{exe}.exe"
    vcvars = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
    src = HERE / folder / "main.cpp"
    if Path(vcvars).exists() and not exe_path.exists():
        cmd = f'call "{vcvars}" && cl /nologo /std:c++20 /O2 /EHsc "{src}" /Fe:"{exe_path}"'
        subprocess.call(cmd, shell=True)
    if exe_path.exists():
        return subprocess.call([str(exe_path), *args])
    # fallback g++
    exe2 = HERE / folder / exe
    if not exe2.exists():
        subprocess.call(["g++", "-O2", "-std=c++20", str(src), "-o", str(exe2)])
    if exe2.exists():
        return subprocess.call([str(exe2), *args])
    print(f"[run] не удалось собрать {name}: нет MSVC vcvars64.bat и нет g++")
    return 1


def run_case(name: str, args: list[str]) -> int:
    target = HERE / "tests" / name / "solve.py"
    if not target.exists():
        print(f"[run] {name}: нет solve.py")
        return 1
    return subprocess.call([sys.executable, str(target), *args])


def new_case(name: str) -> int:
    folder = HERE / "tests" / name
    if folder.exists():
        print(f"[new] {name} уже существует")
        return 1
    folder.mkdir(parents=True)
    skeleton = f'''"""Кейс {name} — заготовка решения.

Переиспользуй шаблоны из папок 01_* .. 10_* (см. ARCHITECTURE.md).
Сюда клади входные файлы и предметную логику.

Запуск: python solve.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent

# генератор ПЗ — из шаблона 10_report_docx_py
sys.path.insert(0, str(HERE.parent.parent / "10_report_docx_py"))
from report import Report  # noqa: E402


def main() -> None:
    # 1) читай входные файлы из HERE
    # 2) применяй шаблоны 01..09
    # 3) собери отчёт
    rep = Report(f"Кейс {name}", "решение")
    rep.section("Результаты")
    rep.paragraph("Здесь будут результаты.", bold=True)
    rep.save(str(HERE / f"{name}_otchet.docx"))
    print("готово")


if __name__ == "__main__":
    main()
'''
    (folder / "solve.py").write_text(skeleton, encoding="utf-8")
    print(f"[new] создан {folder}/solve.py")
    return 0


def usage() -> None:
    print("Шаблоны:")
    for k in TEMPLATES:
        print(f"  {k}")
    cases = list_cases()
    if cases:
        print("\nКейсы:")
        for c in cases:
            print(f"  {c}")
    print("\nКоманды:")
    print("  python run.py run <шаблон|кейс> [args...]")
    print("  python run.py new <caseX>")


def main() -> int:
    args = sys.argv[1:]
    if not args:
        usage()
        return 0
    cmd = args[0]
    if cmd == "run":
        if len(args) < 2:
            usage()
            return 1
        name = args[1]
        rest = args[2:]
        if name in TEMPLATES:
            return run_template(name, rest)
        if name in list_cases():
            return run_case(name, rest)
        print(f"[run] неизвестно: {name}")
        return 1
    if cmd == "new":
        if len(args) < 2:
            usage()
            return 1
        return new_case(args[1])
    if cmd in ("help", "-h", "--help"):
        usage()
        return 0
    usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())
