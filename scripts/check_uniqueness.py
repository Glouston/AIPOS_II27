#!/usr/bin/env python3
"""
Проверка отчётов/проектов студентов на уникальность.

Ожидаемая структура репозитория:
    reports/<Фамилия>/<Номер_лабораторной>/rep/...   -- текст отчёта (pdf/docx/txt/md)
    reports/<Фамилия>/<Номер_лабораторной>/src/...   -- файлы проекта
        (.asm, .pkt, .pcapng, .cfg, .txt и т.п.)

Для каждого изменённого в PR файла:
  1. Побайтовое сравнение (sha256) со всеми файлами того же типа (rep/src) и той же
     лабораторной у ДРУГИХ студентов -> точный дубликат.
  2. Если из файла можно извлечь текст (pdf/docx/txt/md/asm/cfg/...), считается
     TF-IDF + косинусная близость с текстами других студентов по той же лабораторной.

Результат печатается в Markdown (для GITHUB_STEP_SUMMARY) и определяет exit code:
  0 -- проверка пройдена (могут быть предупреждения)
  1 -- найден дубликат/подозрительно высокое сходство (>= fail-threshold)
"""

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

TEXT_EXTENSIONS = {".txt", ".md", ".asm", ".s", ".inc", ".cfg", ".conf", ".log"}
REPORTS_ROOT = Path("reports")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--changed-files", nargs="*", default=[])
    p.add_argument("--fail-threshold", type=float, default=0.90)
    p.add_argument("--warn-threshold", type=float, default=0.60)
    return p.parse_args()


def student_and_lab(path: Path):
    """reports/<surname>/<lab>/(rep|src)/... -> (surname, lab, kind)"""
    parts = path.parts
    if len(parts) < 4 or parts[0] != "reports":
        return None
    surname, lab, kind = parts[1], parts[2], parts[3]
    if kind not in ("rep", "src"):
        return None
    return surname, lab, kind


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_text(path: Path) -> str | None:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        if ext == ".docx":
            import docx

            d = docx.Document(str(path))
            return "\n".join(par.text for par in d.paragraphs)
        if ext in TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::Не удалось извлечь текст из {path}: {e}", file=sys.stderr)
    return None


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def discover_all_files():
    """Собирает все файлы reports/**/{rep,src}/* с их метаданными."""
    files = []
    if not REPORTS_ROOT.exists():
        return files
    for path in REPORTS_ROOT.rglob("*"):
        if not path.is_file():
            continue
        meta = student_and_lab(path)
        if meta is None:
            continue
        surname, lab, kind = meta
        files.append(
            {
                "path": path,
                "surname": surname,
                "lab": lab,
                "kind": kind,
            }
        )
    return files


def find_hash_duplicates(changed_path: Path, all_files, changed_surname, lab, kind):
    changed_hash = sha256_of(changed_path)
    dups = []
    for f in all_files:
        if f["lab"] != lab or f["kind"] != kind:
            continue
        if f["surname"] == changed_surname:
            continue
        if f["path"] == changed_path:
            continue
        try:
            if sha256_of(f["path"]) == changed_hash:
                dups.append(f["path"])
        except OSError:
            continue
    return dups


def find_text_similarities(changed_path: Path, all_files, changed_surname, lab, kind):
    changed_text = extract_text(changed_path)
    if not changed_text or not changed_text.strip():
        return []

    candidates = [
        f
        for f in all_files
        if f["lab"] == lab
        and f["kind"] == kind
        and f["surname"] != changed_surname
        and f["path"] != changed_path
    ]
    if not candidates:
        return []

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    texts = [normalize(changed_text)]
    valid_candidates = []
    for c in candidates:
        t = extract_text(c["path"])
        if t and t.strip():
            texts.append(normalize(t))
            valid_candidates.append(c)

    if not valid_candidates:
        return []

    vectorizer = TfidfVectorizer(token_pattern=r"[^\s]+", min_df=1)
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return []

    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    return list(zip(valid_candidates, sims))


def main():
    args = parse_args()
    changed = [Path(p) for p in args.changed_files if p]
    all_files = discover_all_files()

    findings_fail = []
    findings_warn = []

    for cpath in changed:
        if not cpath.exists():
            # файл удалили в этом же PR
            continue
        meta = student_and_lab(cpath)
        if meta is None:
            continue
        surname, lab, kind = meta

        dups = find_hash_duplicates(cpath, all_files, surname, lab, kind)
        for d in dups:
            findings_fail.append(
                f"**Точный дубликат файла.** `{cpath}` побайтово совпадает с `{d}`."
            )

        sims = find_text_similarities(cpath, all_files, surname, lab, kind)
        for other, score in sims:
            line = f"`{cpath}` похож на `{other['path']}` на **{score:.0%}**."
            if score >= args.fail_threshold:
                findings_fail.append(f"**Высокое текстовое сходство.** {line}")
            elif score >= args.warn_threshold:
                findings_warn.append(line)

    print("## Проверка уникальности отчётов\n")
    if not changed:
        print("Изменённых файлов в `reports/**` не найдено.")
    elif not findings_fail and not findings_warn:
        print("✅ Совпадений с другими сдачами не найдено.")
    else:
        if findings_fail:
            print("### ❌ Найдены дубликаты / подозрительно высокое сходство\n")
            for line in findings_fail:
                print(f"- {line}")
            print()
        if findings_warn:
            print("### ⚠️ Требует ручной проверки (умеренное сходство)\n")
            for line in findings_warn:
                print(f"- {line}")
            print()

    if findings_fail:
        print(
            "\n**Итог: проверка не пройдена.** "
            "Похоже, отчёт/проект не является самостоятельной работой — "
            "требуется ручной разбор перед мержем."
        )
        sys.exit(1)

    print("\n**Итог: проверка пройдена.**")
    sys.exit(0)


if __name__ == "__main__":
    main()
