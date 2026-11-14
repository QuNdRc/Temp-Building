"""Вызов локальной LLM по HTTP с гарантированным JSON на выходе.

Поддержка двух протоколов (переключаются автоматически):
  * OpenAI-совместимый  (llama.cpp llama-server): POST /v1/chat/completions
  * Ollama:                                      POST /api/generate

По умолчанию хост 127.0.0.1:8080 (OpenAI-совместимый).
Запуск:
    python llm.py "Извлеки из текста ..."
    python llm.py --host http://127.0.0.1:8080 --prompt "..."
    python llm.py --host http://127.0.0.1:11434 --ollama --prompt "..."

Идея: просим модель вернуть ТОЛЬКО JSON, а при неудаче парсинга
дотягиваем ответ (отрезаем болтовню, ищем фигурные скобки) и повторяем.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def call_llm(host: str, prompt: str, system: str, ollama: bool,
             model: str, temperature: float, timeout: int) -> str:
    """Один вызов модели, возвращает сырой текст ответа."""
    if ollama:
        url = host.rstrip("/") + "/api/generate"
        payload = {
            "model": model,
            "prompt": f"{system}\n\n{prompt}" if system else prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
    else:
        url = host.rstrip("/") + "/v1/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    if ollama:
        return body.get("response", "")
    return body["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """Вытаскивает первый валидный JSON-объект из текста. Если модель
    обернула ответ в ```json ... ``` или добавила пояснения — срежет лишнее."""
    # пробуем парсить как есть
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # убираем markdown-ограждение
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # ищем первую { ... последнюю } — баланс скобок
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("не удалось извлечь JSON из ответа модели")


def llm_json(host: str, prompt: str, system: str = "", ollama: bool = False,
             model: str = "default", temperature: float = 0.0,
             retries: int = 3, timeout: int = 120) -> dict:
    """Вызывает модель и гарантированно возвращает dict (JSON)."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            text = call_llm(host, prompt, system, ollama, model, temperature, timeout)
            return extract_json(text)
        except Exception as e:  # сеть, таймаут или кривой JSON
            last_err = e
            # на повторных попытках ужесточаем требование к формату
            if attempt < retries:
                prompt = (f"Твой прошлый ответ не был валидным JSON. "
                          f"Ошибка: {e}. Верни ТОЛЬКО валидный JSON, "
                          f"без пояснений и без markdown.\n\n" + prompt)
    raise RuntimeError(f"LLM не вернула валидный JSON за {retries} попыток: {last_err}")


SYSTEM_JSON = ("Ты — парсер документов. Отвечай СТРОГО одним валидным JSON-объектом, "
               "без markdown-ограждений, без пояснений, без текста до и после JSON.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Локальная LLM -> JSON")
    ap.add_argument("prompt", help="что попросить у модели")
    ap.add_argument("--host", default="http://127.0.0.1:8080", help="адрес сервера")
    ap.add_argument("--ollama", action="store_true", help="использовать протокол Ollama")
    ap.add_argument("--model", default="default", help="имя модели")
    ap.add_argument("--system", default=SYSTEM_JSON, help="системный промпт")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    result = llm_json(args.host, args.prompt, args.system, args.ollama,
                      args.model, args.temperature, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
