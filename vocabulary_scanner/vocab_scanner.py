#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
英文文件 CEFR 單詞等級掃描工具
==============================
掃描 PDF、Word、Excel、純文字等檔案，分析英文單詞的 CEFR 等級（A1-C2），
並把 B2 到 C2 的高級單詞/片語整理成「單詞簿」。

輸出（預設寫入 output/ 資料夾）：
    vocabulary_book.xlsx    Excel 單詞簿（含等級統計分頁）
    vocabulary_book.csv     可重複合併的 CSV 單詞簿
    vocabulary_anki.tsv     Anki 匯入檔（單詞、定義、例句、等級）
    vocabulary_eudic.txt    欧路词典/有道等生詞本匯入檔（每行一個單詞）
    vocabulary_book.json    JSON 格式
    analysis_report.txt     完整分析報告

範例：
    python vocab_scanner.py sample/
    python vocab_scanner.py a.pdf b.docx c.xlsx
    python vocab_scanner.py docs/ --merge output/vocabulary_book.csv
    python vocab_scanner.py docs/ --min-level B2 --max-level C2 --top 50
    python vocab_scanner.py --lookup ambiguous
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_RANK = {level: i for i, level in enumerate(LEVEL_ORDER)}

LEVEL_ZH = {
    "A1": "入門 Beginner",
    "A2": "初級 Elementary",
    "B1": "中級 Intermediate",
    "B2": "中高級 Upper-Intermediate",
    "C1": "高級 Advanced",
    "C2": "精通 Proficiency",
}

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".txt": "text",
    ".csv": "text",
    ".tsv": "text",
    ".md": "text",
    ".markdown": "text",
    ".html": "text",
    ".htm": "text",
}

WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[’'\u2010\u2011-][A-Za-zÀ-ÖØ-öø-ÿ]+)*"
)

HERE = os.path.dirname(os.path.abspath(__file__))
OCR_SWIFT = os.path.join(HERE, "ocr", "vision_ocr.swift")
OCR_BIN = os.path.join(HERE, "build", "vision_ocr")


def normalize(text: str) -> str:
    """小寫、去除重音符號，保留字母、數字、連字號、撇號與空白。"""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = "".join(ch for ch in text if ch.isalpha() or ch.isdigit() or ch in " '-")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" '-")


# ---------------------------------------------------------------------------
# CEFR 字典
# ---------------------------------------------------------------------------

class CefrDictionary:
    """載入 data/cefr_words.csv，提供單詞與片語的等級查詢。"""

    def __init__(self, path: str):
        self.words = defaultdict(lambda: {"levels": set(), "pos": set()})
        self.phrases = defaultdict(lambda: {"levels": set(), "pos": set()})

        if not os.path.exists(path):
            print(f"❌ 找不到 CEFR 字典：{path}")
            print("   請先執行 build_dictionary.py 產生，或指定 --dictionary 參數。")
            sys.exit(1)

        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                word = (row.get("word") or "").strip()
                level = (row.get("level") or "").strip().upper()
                pos = (row.get("pos") or "").strip()
                kind = (row.get("type") or "word").strip()
                if not word or level not in LEVEL_RANK:
                    continue
                bucket = self.phrases if kind == "phrase" else self.words
                bucket[word]["levels"].add(level)
                if pos:
                    bucket[word]["pos"].add(pos)

    @staticmethod
    def primary_level(levels) -> str:
        return min(levels, key=LEVEL_RANK.get)

    def lookup_word(self, token: str, lemmatizer=None):
        """回傳 (詞條, 主要等級, 全部等級, 詞性集合) 或 None。"""
        for candidate in token_candidates(token, lemmatizer):
            if candidate in self.words:
                info = self.words[candidate]
                return (
                    candidate,
                    self.primary_level(info["levels"]),
                    tuple(sorted(info["levels"], key=LEVEL_RANK.get)),
                    tuple(sorted(info["pos"])),
                )
        return None

    def lookup_phrase(self, phrase: str):
        phrase = normalize(phrase)
        if phrase in self.phrases:
            info = self.phrases[phrase]
            return (
                phrase,
                self.primary_level(info["levels"]),
                tuple(sorted(info["levels"], key=LEVEL_RANK.get)),
                tuple(sorted(info["pos"])),
            )
        return None


def token_candidates(token: str, lemmatizer=None):
    """回傳 token 的候選形式：原形、去連字號、WordNet 詞形還原。"""
    base = normalize(token)
    candidates = [base]
    if "-" in base:
        candidates.append(base.replace("-", ""))

    if lemmatizer is not None:
        for pos in ("n", "v", "a", "r"):
            try:
                lemma = lemmatizer.lemmatize(base, pos=pos)
            except Exception:
                continue
            variants = {lemma}
            if "-" in lemma:
                variants.add(lemma.replace("-", ""))
            for variant in variants:
                if variant and variant not in candidates:
                    candidates.append(variant)
    # 副詞後備：WordNet 不會把 'coherently' 還原成 'coherent'，
    # 當原詞不在字典時，嘗試去掉 -ly 再比對（只在查得到時才會命中）。
    if len(base) > 4 and base.endswith("ly"):
        stripped = base[:-2]
        if stripped not in candidates:
            candidates.append(stripped)
    return candidates


# ---------------------------------------------------------------------------
# NLTK / WordNet（可選，提供詞形還原與英文定義）
# ---------------------------------------------------------------------------

def setup_nltk(enable: bool = True):
    """嘗試載入 NLTK。成功回傳 (lemmatizer, wordnet)，失敗回傳 (None, None)。"""
    if not enable:
        return None, None
    try:
        import nltk
        from nltk.corpus import wordnet as wn
        from nltk.stem import WordNetLemmatizer
    except ImportError:
        print("⚠️  未安裝 nltk（pip install nltk）。將跳過詞形還原與英文定義。")
        return None, None

    try:
        wn.synsets("test")
    except Exception:
        try:
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
            wn.synsets("test")
        except Exception:
            print("⚠️  無法下載 WordNet 資料。將跳過詞形還原與英文定義。")
            return None, None

    return WordNetLemmatizer(), wn


POS_TO_WN = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "r"}
WN_TO_POS = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}


def lookup_definition(wordnet, word: str, preferred_pos: tuple):
    """回傳 (英文定義, WordNet 例句) 或 (None, None)。"""
    if wordnet is None:
        return None, None
    synsets = wordnet.synsets(word)
    if not synsets and "-" in word:
        synsets = wordnet.synsets(word.replace("-", ""))
    if not synsets:
        return None, None

    wanted = set()
    for pos in preferred_pos:
        if pos in POS_TO_WN:
            wanted.add(POS_TO_WN[pos])
    if wanted:
        filtered = [s for s in synsets if s.pos() in wanted]
        if filtered:
            synsets = filtered

    best = synsets[0]
    definition = best.definition()
    example = None
    if best.examples():
        example = best.examples()[0]
    return definition, example


# ---------------------------------------------------------------------------
# OCR（macOS 專用：Apple Vision，認字前先把 PDF 頁面渲染成圖片）
# ---------------------------------------------------------------------------

def _ensure_ocr_binary():
    """回傳 OCR 執行檔路徑；不存在或無法編譯時回傳 None。"""
    if os.path.exists(OCR_BIN):
        return OCR_BIN
    swiftc = shutil.which("swiftc")
    if not swiftc or not os.path.exists(OCR_SWIFT):
        return None
    os.makedirs(os.path.dirname(OCR_BIN), exist_ok=True)
    cache = os.path.join(tempfile.gettempdir(), "vocab_swift_module_cache")
    os.makedirs(cache, exist_ok=True)
    try:
        subprocess.run(
            [swiftc, "-O", "-module-cache-path", cache, OCR_SWIFT, "-o", OCR_BIN],
            check=True, capture_output=True,
        )
    except Exception:
        return None
    return OCR_BIN if os.path.exists(OCR_BIN) else None


def ocr_binary_ready():
    """檢查 OCR 是否可用（不觸發編譯；真正要用時才在 _ensure_ocr_binary 編譯）。"""
    if os.path.exists(OCR_BIN):
        return True
    return shutil.which("swiftc") is not None and os.path.exists(OCR_SWIFT)


def _render_pdf_pages(path: str, dpi: int = 200):
    """把 PDF 每一頁渲染成 PNG，回傳 (圖片路徑清單, 暫存資料夾)。"""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return [], None

    tmp = tempfile.mkdtemp(prefix="vocab_ocr_")
    images = []
    try:
        document = pdfium.PdfDocument(path)
        scale = dpi / 72.0
        for i in range(len(document)):
            try:
                bitmap = document[i].render(scale=scale)
                image = bitmap.to_pil()
                img_path = os.path.join(tmp, f"page_{i + 1:04d}.png")
                image.save(img_path)
                images.append(img_path)
            except Exception:
                continue
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return [], None
    return images, tmp


def ocr_pdf_pages(path: str, dpi: int = 200) -> str:
    """對 PDF 逐頁 OCR，回傳合併文字。"""
    binary = _ensure_ocr_binary()
    if not binary:
        return ""
    images, tmp = _render_pdf_pages(path, dpi)
    if not images:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return ""
    parts = []
    try:
        for img_path in images:
            proc = subprocess.run([binary, img_path], capture_output=True, text=True)
            if proc.stdout:
                parts.append(proc.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "\n".join(parts)


def ocr_image_file(path: str) -> str:
    """對單一圖片檔 OCR，回傳文字。"""
    binary = _ensure_ocr_binary()
    if not binary:
        return ""
    proc = subprocess.run([binary, path], capture_output=True, text=True)
    return proc.stdout or ""


# ---------------------------------------------------------------------------
# 翻譯（只翻單詞本身，不翻定義；結果會快取，之後離線也能用）
# ---------------------------------------------------------------------------

LANG_ALIASES = {
    # 繁體中文
    "中文": "zh-TW", "繁體中文": "zh-TW", "繁體": "zh-TW", "繁中": "zh-TW",
    "zh": "zh-TW", "zh-tw": "zh-TW", "zh-hant": "zh-TW", "zh-hk": "zh-TW", "zh-mo": "zh-TW",
    # 簡體中文
    "簡體中文": "zh-CN", "簡體": "zh-CN", "簡中": "zh-CN", "zh-cn": "zh-CN", "zh-hans": "zh-CN",
    # 其他常見語言
    "日文": "ja", "日語": "ja", "japanese": "ja",
    "韓文": "ko", "韓語": "ko", "korean": "ko",
    "西班牙文": "es", "西班牙語": "es", "spanish": "es",
    "法文": "fr", "法語": "fr", "french": "fr",
    "德文": "de", "德語": "de", "german": "de",
    "義大利文": "it", "意大利文": "it", "義語": "it", "italian": "it",
    "葡萄牙文": "pt", "葡語": "pt", "portuguese": "pt",
    "俄文": "ru", "俄語": "ru", "russian": "ru",
    "泰文": "th", "泰語": "th", "thai": "th",
    "越南文": "vi", "越南語": "vi", "vietnamese": "vi",
    "印尼文": "id", "印尼語": "id", "indonesian": "id",
    "阿拉伯文": "ar", "阿拉伯語": "ar", "arabic": "ar",
}


def resolve_language(name: str) -> str:
    """把常見語言名稱換成 Google 翻譯語言代碼。"""
    if not name:
        return name
    return LANG_ALIASES.get(name.strip().lower(), name.strip())


def translation_cache_path(lang: str) -> str:
    return os.path.join(HERE, "data", "translations", f"{lang}.json")


def load_translation_cache(lang: str) -> dict:
    path = translation_cache_path(lang)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_translation_cache(lang: str, cache: dict):
    path = translation_cache_path(lang)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def translate_words(words, target_lang: str, source: str = "en") -> dict:
    """把一批單詞翻譯成目標語言，回傳 {word: translation}（含快取）。"""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("⚠️  未安裝 deep-translator（pip install deep-translator），略過翻譯。")
        return {}

    cache = load_translation_cache(target_lang)
    missing = [w for w in words if w not in cache or not cache[w]]
    if not missing:
        return cache

    translator = GoogleTranslator(source=source, target=target_lang)
    chunk_size = 40
    for i in range(0, len(missing), chunk_size):
        chunk = missing[i : i + chunk_size]
        try:
            translated = translator.translate_batch(chunk)
        except Exception:
            translated = []
            for word in chunk:
                try:
                    translated.append(translator.translate(word))
                    time.sleep(0.15)
                except Exception:
                    translated.append("")
        for word, value in zip(chunk, translated):
            if value:  # 只有成功翻譯才寫入快取，避免留下空值
                cache[word] = value
        if any(cache[w] for w in chunk):
            save_translation_cache(target_lang, cache)
        if i + chunk_size < len(missing):
            time.sleep(0.4)
    return cache


# ---------------------------------------------------------------------------
# 檔案讀取
# ---------------------------------------------------------------------------

def read_text_file(path: str) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "gb18030", "big5"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ""


def read_pdf_file(path: str, ocr_mode: str = "auto", ocr_dpi: int = 200) -> str:
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as exc:
        print(f"⚠️  pdfplumber 讀取失敗（{exc}），嘗試 pypdf…")
    if text.strip():
        return text
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    except Exception as exc:
        print(f"❌ 讀取 PDF 失敗：{exc}")

    if ocr_mode == "off":
        return text

    # auto：文字層幾乎為空（掃描圖片）時才走 OCR；force：一律 OCR
    needs_ocr = ocr_mode == "force" or len(text.strip()) < 40
    if not needs_ocr:
        return text

    ocr_text = ocr_pdf_pages(path, dpi=ocr_dpi)
    if ocr_text.strip():
        return ocr_text
    if not ocr_binary_ready():
        print("⚠️  此 PDF 沒有文字層，且 OCR 未啟用（macOS 需有 Xcode 指令列工具）。")
    return text


def read_docx_file(path: str) -> str:
    try:
        import docx
        document = docx.Document(path)
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except Exception as exc:
        print(f"❌ 讀取 Word 失敗：{exc}")
        return ""


def read_xlsx_file(path: str) -> str:
    try:
        import openpyxl
        workbook = openpyxl.load_workbook(path, data_only=True)
        parts = []
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            for row in sheet.iter_rows(values_only=True):
                cells = [str(cell) for cell in row if cell is not None]
                if cells:
                    parts.append(" ".join(cells))
        return "\n".join(parts)
    except Exception as exc:
        print(f"❌ 讀取 Excel 失敗：{exc}")
        return ""


def extract_text(path: str, ocr_mode: str = "auto", ocr_dpi: int = 200) -> str:
    ext = os.path.splitext(path)[1].lower()
    kind = SUPPORTED_EXTENSIONS.get(ext)
    if kind == "pdf":
        return read_pdf_file(path, ocr_mode, ocr_dpi)
    if kind == "image":
        return ocr_image_file(path)
    if kind == "docx":
        return read_docx_file(path)
    if kind == "xlsx":
        return read_xlsx_file(path)
    if kind == "text":
        return read_text_file(path)
    print(f"⚠️  跳過不支援的檔案類型：{path}")
    return ""


def collect_input_files(inputs):
    """把輸入參數展開成支援檔案的清單（可含資料夾，遞迴搜尋）。"""
    files = []
    for item in inputs:
        if os.path.isdir(item):
            for root, _dirs, names in os.walk(item):
                for name in sorted(names):
                    if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                        files.append(os.path.join(root, name))
        elif os.path.isfile(item):
            files.append(item)
        else:
            print(f"⚠️  找不到：{item}")
    return files


# ---------------------------------------------------------------------------
# 文字分析
# ---------------------------------------------------------------------------

def split_sentences(text: str):
    """把文字拆成句子（保留段落，但把段內換行當成空白，避免硬換行截斷句子）。"""
    text = text.replace("\r", "\n")
    sentences = []
    for paragraph in re.split(r"\n\s*\n+", text):
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if not paragraph:
            continue
        for part in re.split(r"(?<=[.!?…])\s+", paragraph):
            part = part.strip()
            if part and re.search(r"[A-Za-z]", part):
                if len(part) > 240:
                    part = part[:240].rstrip() + "…"
                sentences.append(part)
    return sentences


@dataclass
class Entry:
    word: str
    level: str
    all_levels: tuple
    pos: tuple
    kind: str  # word / phrase
    count: int = 0
    sources: set = field(default_factory=set)
    example: str = ""
    definition: str = ""
    wordnet_example: str = ""
    translation: str = ""


def scan_text(text: str, dictionary: CefrDictionary, lemmatizer, source_label: str):
    """分析一段文字，回傳 (entries, level_token_counts, level_unique_words, unknown)。"""
    entries = {}
    level_token_counts = Counter()
    level_unique_words = defaultdict(set)
    unknown = Counter()

    for sentence in split_sentences(text):
        tokens = WORD_RE.findall(sentence)

        # 單詞分析
        for token in tokens:
            hit = dictionary.lookup_word(token, lemmatizer)
            if hit:
                word, level, all_levels, pos = hit
                level_token_counts[level] += 1
                level_unique_words[level].add(word)
                entry = entries.setdefault(
                    (word, "word"),
                    Entry(word, level, all_levels, pos, "word"),
                )
                entry.count += 1
                entry.sources.add(source_label)
                if not entry.example:
                    entry.example = sentence
            else:
                unknown[normalize(token)] += 1

        # 片語分析（先配對較長片語，避免重複計算）
        covered = set()
        for n in (4, 3, 2):
            for i in range(len(tokens) - n + 1):
                if any(j in covered for j in range(i, i + n)):
                    continue
                phrase = " ".join(tokens[i : i + n])
                hit = dictionary.lookup_phrase(phrase)
                if hit:
                    word, level, all_levels, pos = hit
                    entry = entries.setdefault(
                        (word, "phrase"),
                        Entry(word, level, all_levels, pos, "phrase"),
                    )
                    entry.count += 1
                    entry.sources.add(source_label)
                    if not entry.example:
                        entry.example = sentence
                    covered.update(range(i, i + n))

    return entries, level_token_counts, level_unique_words, unknown


# ---------------------------------------------------------------------------
# 匯出
# ---------------------------------------------------------------------------

def pos_text(pos: tuple) -> str:
    mapping = {
        "noun": "n.", "verb": "v.", "adjective": "adj.",
        "adverb": "adv.", "preposition": "prep.", "determiner": "det.",
        "pronoun": "pron.", "conjunction": "conj.", "interjection": "interj.",
        "number": "num.", "numeral": "num.", "phrasal verb": "phr. v.",
        "auxiliary verb": "aux.", "modal verb": "mod.", "modal auxiliary": "mod.",
        "be-verb": "be v.", "do-verb": "do v.", "have-verb": "have v.",
        "infinitive-to": "to-inf.", "vern": "v.",
    }
    return "/".join(mapping.get(p, p) for p in pos) if pos else ""


def book_rows(entries, sort_key="level"):
    rows = []
    for entry in entries:
        rows.append(
            {
                "word": entry.word,
                "translation": entry.translation,
                "type": "片語" if entry.kind == "phrase" else "單詞",
                "level": entry.level,
                "pos": "/".join(entry.pos),
                "pos_short": pos_text(entry.pos),
                "all_levels": "/".join(entry.all_levels),
                "count": entry.count,
                "sources": "; ".join(sorted(entry.sources)),
                "definition": entry.definition,
                "example": entry.example,
            }
        )
    if sort_key == "level":
        rows.sort(key=lambda r: (LEVEL_RANK[r["level"]], r["type"], r["word"]))
    else:  # 次數
        rows.sort(key=lambda r: (-r["count"], LEVEL_RANK[r["level"]], r["word"]))
    return rows


def write_csv_book(rows, path):
    fieldnames = [
        "word", "translation", "type", "level", "pos", "pos_short", "all_levels",
        "count", "sources", "definition", "example",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx_book(rows, stats, path):
    import openpyxl
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "B2-C2 單詞簿"

    headers = ["單詞/片語", "翻譯", "類型", "等級(CEFR)", "詞性", "出現次數", "來源檔案", "英文定義", "例句"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        sheet.append(
            [
                row["word"],
                row["translation"],
                row["type"],
                row["level"],
                row["pos_short"],
                row["count"],
                row["sources"],
                row["definition"],
                row["example"],
            ]
        )

    widths = [22, 20, 8, 10, 12, 9, 26, 48, 48]
    for i, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(i)].width = width
    sheet.freeze_panes = "A2"

    stats_sheet = workbook.create_sheet("等級統計")
    stats_sheet.append(["等級", "說明", "總出現次數", "不同單詞數"])
    for level in LEVEL_ORDER:
        stats_sheet.append(
            [
                level,
                LEVEL_ZH[level],
                stats["token_counts"].get(level, 0),
                len(stats["unique_words"].get(level, set())),
            ]
        )
    stats_sheet.append(["未知", "不在字典中", sum(stats["unknown"].values()), len(stats["unknown"])])
    stats_sheet.append(["總計", "", stats["total_tokens"], stats["total_unique_tokens"]])
    for cell in stats_sheet[1]:
        cell.font = Font(bold=True)
    for i, width in enumerate([10, 30, 14, 14], 1):
        stats_sheet.column_dimensions[get_column_letter(i)].width = width

    workbook.save(path)


def write_anki_tsv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for row in rows:
            definition = row["definition"] or ""
            example = row["example"] or ""
            translation = row["translation"] or ""
            f.write(
                f"{row['word']}\t{definition}\t{example}\t{row['level']}\t"
                f"{row['pos_short']}\t{translation}\n"
            )


def write_eudic_txt(rows, path):
    level_of = {row["word"]: row["level"] for row in rows}
    words = sorted(
        {row["word"] for row in rows if row["type"] == "單詞"},
        key=lambda w: (LEVEL_RANK.get(level_of.get(w, "C2"), 99), w),
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(words) + ("\n" if words else ""))


def write_json_book(rows, path):
    payload = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_entries": len(rows),
        },
        "entries": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_report(rows, stats, unknown_top, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("英文文件 CEFR 單詞等級分析報告\n")
        f.write("=" * 52 + "\n")
        f.write(f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"總單詞數：{stats['total_tokens']:,}\n")
        f.write(f"不同單詞數：{stats['total_unique_tokens']:,}\n\n")

        f.write("各等級統計：\n")
        f.write("-" * 52 + "\n")
        for level in LEVEL_ORDER:
            count = stats["token_counts"].get(level, 0)
            unique = len(stats["unique_words"].get(level, set()))
            pct = (count / stats["total_tokens"] * 100) if stats["total_tokens"] else 0
            f.write(f"{level} ({LEVEL_ZH[level]}): 出現 {count:,} 次 ({pct:.1f}%)，不同單詞 {unique}\n")
        unknown_count = sum(stats["unknown"].values())
        f.write(f"未知: {unknown_count:,} 次（{len(stats['unknown'])} 個不同單詞）\n\n")

        f.write("B2-C2 高級單詞簿：\n")
        f.write("-" * 52 + "\n")
        current = None
        for row in rows:
            if row["level"] != current:
                current = row["level"]
                f.write(f"\n[{current}] {LEVEL_ZH[current]}：\n")
            definition = f" — {row['definition']}" if row["definition"] else ""
            translation = f"【{row['translation']}】" if row["translation"] else ""
            f.write(f"  {row['word']}{translation} ({row['pos_short'] or '無詞性'}) x{row['count']}{definition}\n")

        if unknown_top:
            f.write("\n最常出現的未知單詞：\n")
            f.write("-" * 52 + "\n")
            for word, count in unknown_top:
                f.write(f"  {word}: {count} 次\n")


# ---------------------------------------------------------------------------
# 合併
# ---------------------------------------------------------------------------

def load_book_csv(path):
    entries = {}
    if not os.path.exists(path):
        return entries
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            word = (row.get("word") or "").strip()
            kind = "phrase" if row.get("type") == "片語" else "word"
            entry = Entry(
                word=word,
                level=(row.get("level") or "C2").strip(),
                all_levels=tuple((row.get("all_levels") or "").split("/")),
                pos=tuple(filter(None, (row.get("pos") or "").split("/"))),
                kind=kind,
                count=int(row.get("count") or 0),
                sources=set(filter(None, (row.get("sources") or "").split("; "))),
                example=row.get("example") or "",
                definition=row.get("definition") or "",
                translation=row.get("translation") or "",
            )
            entries[(word, kind)] = entry
    return entries


def merge_entries(old: dict, new: dict):
    for key, entry in new.items():
        if key in old:
            target = old[key]
            target.count += entry.count
            target.sources |= entry.sources
            target.example = target.example or entry.example
            target.definition = target.definition or entry.definition
            target.translation = target.translation or entry.translation
            target.all_levels = tuple(sorted(set(target.all_levels) | set(entry.all_levels), key=LEVEL_RANK.get))
        else:
            old[key] = entry
    return old


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------

def print_summary(rows, stats):
    print("\n" + "=" * 60)
    print("📊 掃描完成")
    print("=" * 60)
    print(f"總單詞數：{stats['total_tokens']:,}    不同單詞：{stats['total_unique_tokens']:,}")
    print("-" * 60)
    for level in LEVEL_ORDER:
        count = stats["token_counts"].get(level, 0)
        unique = len(stats["unique_words"].get(level, set()))
        if count or unique:
            pct = (count / stats["total_tokens"] * 100) if stats["total_tokens"] else 0
            print(f"  {level}  {LEVEL_ZH[level]:<22} 出現 {count:>6,} 次 ({pct:>5.1f}%)，不同單詞 {unique}")
    print(f"  未知  不在字典中               出現 {sum(stats['unknown'].values()):>6,} 次，不同單詞 {len(stats['unknown'])}")
    print("-" * 60)
    by_level = Counter(r["level"] for r in rows)
    print(f"✅ 收集到 B2-C2 高級詞彙：{len(rows)} 筆（B2 {by_level.get('B2', 0)}、C1 {by_level.get('C1', 0)}、C2 {by_level.get('C2', 0)}）")


def main():
    parser = argparse.ArgumentParser(
        description="掃描英文文件，分析單詞 CEFR 等級，並匯出 B2-C2 單詞簿。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "支援格式：PDF (.pdf)、Word (.docx)、Excel (.xlsx)、圖片 (.png/.jpg/.tiff)、"
            "純文字 (.txt/.csv/.md/.html)\n"
            "範例：\n"
            "  python vocab_scanner.py sample/\n"
            "  python vocab_scanner.py a.pdf b.docx --merge output/vocabulary_book.csv\n"
            "  python vocab_scanner.py sample/ --translate zh-TW\n"
            "  python vocab_scanner.py --lookup ambiguous\n"
        ),
    )
    parser.add_argument("inputs", nargs="*", help="檔案或資料夾（可多個；資料夾會遞迴掃描）")
    parser.add_argument("--out-dir", default=os.path.join(HERE, "output"), help="輸出資料夾")
    parser.add_argument("--dictionary", default=os.path.join(HERE, "data", "cefr_words.csv"), help="CEFR 字典 CSV")
    parser.add_argument("--min-level", default="B2", choices=LEVEL_ORDER, help="單詞簿最低等級（預設 B2）")
    parser.add_argument("--max-level", default="C2", choices=LEVEL_ORDER, help="單詞簿最高等級（預設 C2）")
    parser.add_argument("--top", type=int, default=30, help="報告中每等級/未知單詞顯示數量（預設 30）")
    parser.add_argument("--no-definitions", action="store_true", help="不查詢 WordNet 英文定義")
    parser.add_argument("--merge", help="合併進既有的單詞簿 CSV（累加次數與來源）")
    parser.add_argument("--sort", choices=["level", "count"], default="level", help="單詞簿排序方式")
    parser.add_argument("--lookup", help="查詢一個單詞的 CEFR 等級後離開")
    parser.add_argument(
        "--ocr", choices=["auto", "force", "off"], default="auto",
        help="OCR 模式：auto=PDF 沒有文字層才用 OCR；force=PDF 一律 OCR；off=關閉（預設 auto）",
    )
    parser.add_argument("--ocr-dpi", type=int, default=200, help="OCR 時 PDF 渲染解析度（預設 200）")
    parser.add_argument(
        "--translate", default=None,
        help="把單詞翻譯成指定語言（例如 zh-TW、zh-CN、ja、ko、es、fr；只翻單詞本身）",
    )
    args = parser.parse_args()

    dictionary = CefrDictionary(args.dictionary)
    lemmatizer, wordnet = setup_nltk(enable=not args.no_definitions)

    # OCR 狀態提示
    if args.ocr != "off":
        if ocr_binary_ready():
            print(f"🖼️  OCR 已啟用（模式：{args.ocr}，DPI：{args.ocr_dpi}）")
        else:
            print("⚠️  OCR 未啟用：掃描圖片的 PDF 會被跳過。")

    # 單詞查詢模式
    if args.lookup:
        hit = dictionary.lookup_word(args.lookup, lemmatizer)
        if hit:
            word, level, all_levels, pos = hit
            print(f"✅ '{word}'  等級：{level} ({LEVEL_ZH[level]})")
            print(f"   全部等級：{'/'.join(all_levels)}   詞性：{'/'.join(pos) or '未標註'}")
            definition, _ = lookup_definition(wordnet, word, pos)
            if definition:
                print(f"   定義：{definition}")
            if args.translate:
                target = resolve_language(args.translate)
                translation = translate_words([word], target).get(word, "")
                if translation:
                    print(f"   翻譯({target})：{translation}")
        else:
            print(f"❌ 在 CEFR 字典中找不到 '{args.lookup}'（可能不在 B2-C2 範圍或不在字典中）。")
        return

    files = collect_input_files(args.inputs)
    if not files:
        print("❌ 沒有可掃描的檔案。請提供 PDF/Word/Excel/文字檔案或資料夾。")
        return

    print(f"📂 準備掃描 {len(files)} 個檔案…")

    all_entries = {}
    token_counts = Counter()
    unique_words = defaultdict(set)
    unknown = Counter()

    for path in files:
        label = os.path.relpath(path, os.getcwd())
        print(f"   掃描中：{label}")
        text = extract_text(path, ocr_mode=args.ocr, ocr_dpi=args.ocr_dpi)
        if not text.strip():
            print(f"   ⚠️  沒有擷取到文字，跳過：{label}")
            continue
        file_entries, f_token, f_unique, f_unknown = scan_text(text, dictionary, lemmatizer, label)
        all_entries = merge_entries(all_entries, file_entries)
        token_counts.update(f_token)
        for level, words in f_unique.items():
            unique_words[level] |= words
        unknown.update(f_unknown)

    unknown_tokens = sum(unknown.values())
    total_tokens = sum(token_counts.values()) + unknown_tokens
    total_unique_tokens = sum(len(words) for words in unique_words.values()) + len(unknown)

    # 篩選 B2-C2
    min_rank, max_rank = LEVEL_RANK[args.min_level], LEVEL_RANK[args.max_level]
    selected = [
        entry
        for entry in all_entries.values()
        if min_rank <= LEVEL_RANK[entry.level] <= max_rank
    ]

    # 英文定義
    if not args.no_definitions:
        print("🔎 查詢英文定義（WordNet）…")
        for entry in selected:
            if entry.kind == "word" and not entry.definition:
                definition, example = lookup_definition(wordnet, entry.word, entry.pos)
                if definition:
                    entry.definition = definition
                if example:
                    entry.wordnet_example = example

    # 合併既有單詞簿
    if args.merge:
        existing = load_book_csv(args.merge)
        selected_map = {(e.word, e.kind): e for e in selected}
        selected = list(merge_entries(existing, selected_map).values())
        print(f"🔗 已合併既有單詞簿：{args.merge}")

    # 翻譯（只翻單詞本身，不翻定義）
    if args.translate:
        target = resolve_language(args.translate)
        words = sorted({e.word for e in selected})
        print(f"🌐 翻譯為 {target}（{len(words)} 個詞，快取於 data/translations/）…")
        translation = translate_words(words, target)
        for entry in selected:
            if not entry.translation:
                entry.translation = translation.get(entry.word, "")
        if not translation:
            print("   ⚠️  未取得任何翻譯（請確認已連上網路並安裝 deep-translator）。")

    rows = book_rows(selected, sort_key=args.sort)

    os.makedirs(args.out_dir, exist_ok=True)
    xlsx_path = os.path.join(args.out_dir, "vocabulary_book.xlsx")
    csv_path = os.path.join(args.out_dir, "vocabulary_book.csv")
    anki_path = os.path.join(args.out_dir, "vocabulary_anki.tsv")
    eudic_path = os.path.join(args.out_dir, "vocabulary_eudic.txt")
    json_path = os.path.join(args.out_dir, "vocabulary_book.json")
    report_path = os.path.join(args.out_dir, "analysis_report.txt")

    stats = {
        "token_counts": token_counts,
        "unique_words": unique_words,
        "unknown": unknown,
        "total_tokens": total_tokens,
        "total_unique_tokens": total_unique_tokens,
    }
    unknown_top = unknown.most_common(args.top)

    write_xlsx_book(rows, stats, xlsx_path)
    write_csv_book(rows, csv_path)
    write_anki_tsv(rows, anki_path)
    write_eudic_txt(rows, eudic_path)
    write_json_book(rows, json_path)
    write_report(rows, stats, unknown_top, report_path)

    print("\n📁 輸出檔案：")
    for name in ("vocabulary_book.xlsx", "vocabulary_book.csv", "vocabulary_anki.tsv", "vocabulary_eudic.txt", "vocabulary_book.json", "analysis_report.txt"):
        print(f"   - {os.path.join(args.out_dir, name)}")

    print_summary(rows, stats)


if __name__ == "__main__":
    main()
