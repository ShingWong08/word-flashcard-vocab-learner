#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 CEFR-J / Octanove 原始詞表整理成 vocab_scanner.py 使用的字典檔。

資料來源（可免費使用，詳見 data/SOURCES.md）：
  1. CEFR-J Vocabulary Profile (ver 1.5)         -> A1, A2, B1, B2
  2. Octanove Vocabulary Profile C1/C2 (ver 1.0) -> C1, C2

用法：
    python build_dictionary.py \
        cefrj-vocabulary-profile-1.5.csv \
        octanove-vocabulary-profile-c1c2-1.0.csv \
        -o data/cefr_words.csv
"""

import argparse
import csv
import re
import unicodedata


def normalize(word: str) -> str:
    """小寫、去除重音符號，只保留字母、數字、空白、連字號與撇號。"""
    word = unicodedata.normalize("NFKD", word)
    word = "".join(ch for ch in word if not unicodedata.combining(ch))
    word = word.lower()
    # 只保留英文字母、數字、空白、連字號、撇號；其餘（含標點）移除
    word = "".join(ch for ch in word if ch.isalpha() or ch.isdigit() or ch in " '-")
    word = word.strip(" '-")
    word = re.sub(r"\s+", " ", word)
    return word.strip()


def expand_headword(headword: str):
    """把 'agonize/agonise'、'wornout/worn out/worn-out' 拆成多個形式。"""
    for form in headword.split("/"):
        form = form.strip()
        form = normalize(form)
        if form:
            yield form


def main():
    parser = argparse.ArgumentParser(description="整理 CEFR 詞表為單一字典 CSV")
    parser.add_argument("sources", nargs="+", help="原始 CEFR CSV 檔案路徑")
    parser.add_argument("-o", "--output", default="data/cefr_words.csv")
    args = parser.parse_args()

    entries = {}  # (word, pos, level, type) -> True
    for path in args.sources:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                level = (row.get("CEFR") or "").strip().upper()
                if level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
                    continue
                pos = (row.get("pos") or "").strip().lower() or ""
                for form in expand_headword(row.get("headword") or ""):
                    kind = "phrase" if " " in form else "word"
                    entries[(form, pos, level, kind)] = True

    rows = sorted(
        ({"word": w, "pos": p, "level": l, "type": t} for (w, p, l, t) in entries),
        key=lambda r: (r["type"], r["word"], r["level"], r["pos"]),
    )

    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["word", "pos", "level", "type"])
        writer.writeheader()
        writer.writerows(rows)

    n_words = sum(1 for r in rows if r["type"] == "word")
    n_phrases = sum(1 for r in rows if r["type"] == "phrase")
    print(f"已寫入 {args.output}：單詞 {n_words} 筆、片語 {n_phrases} 筆，共 {len(rows)} 筆")


if __name__ == "__main__":
    main()
