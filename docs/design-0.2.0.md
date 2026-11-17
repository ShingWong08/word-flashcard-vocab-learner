# 0.2.0 設計文件：由「能 install 的殼」變成「可發佈的自適應單詞卡套件」

- 日期：2026-11-17
- 截止：2026-11-22（5 天）
- 目標版本：`word-flashcard-vocab-learner==0.2.0`
- 決策者：TAM Lok Yan Andy、ShingWong08、Kristy-Chong

---

## 1. 意圖

現在 repo 裡有兩個互不相干的東西：`src/word_flashcard_vocab_learner/`（320 行、CLI 是 stub、裝完只印兩行）
和 `vocabulary_scanner/`（1034 行、真的能跑、但沒有被打包、也沒接上套件）。

0.2.0 要做的是：**把 scanner 變成套件的核心能力，補上真正的單詞卡資料模型與複習排程，
讓 `pip install word-flashcard-vocab-learner` 之後，在 JupyterHub 上貼三行就能完成
「掃描我的講義 → 生出牌組 → 複習 → 看記憶預測」**。

## 2. 評分表 → 設計約束

| 評分項 | 它實際要求的 | 設計約束 |
|---|---|---|
| published | PyPI 有頁面、repo 有版本 | 0.2.0 必須 build + upload + tag，且 `pip install` 直接可用 |
| documented | 公開文件 | 根 README 完整 + `docs/` 發佈到 GitHub Pages |
| functional | JupyterHub 上安裝無衝突、當場演示 | **核心零依賴**；演示在 notebook 完成；語音／PDF／AI 全部 optional |
| innovative | 現有套件不易取代 | 賣點是「CEFR 自適應牌組編譯器」，不是又一個 Anki |
| teamwork | 規律 commit、多人共同演示 | 檔案邊界按人切分，每人一個可獨立講的模組 |

## 3. 四個關鍵決定

1. **notebook-first，CLI 為輔。**
   演示場地是 JupyterHub，終端 TUI 沒法演示。核心 API 必須在 cell 裡三行跑完，
   卡片用 HTML（`IPython.display`）渲染；沒有 IPython 時退回純文字。

2. **核心零第三方依賴。**
   `openai` 會拉 pydantic/httpx，是 JupyterHub image 最常見的衝突源，直接刪掉。
   PDF/Word 抽取、AI、語音都放進 extras，不裝就不載入、不影響安裝。

3. **賣點是「從你的教材編譯牌組」，不是 SRS。**
   Anki 已有間隔複習，做一樣的東西拿不到 innovative。獨特的是：
   `Deck.from_document()` 讀你的講義 → CEFR 分級 → 只留你未掌握且 ≥ 指定等級的字
   → 每張卡附上**它出現在你教材裡的那一句**。這個組合沒有現成套件提供。

4. **全程離線可用。**
   演示現場網路不可控。CEFR 詞表打包進 wheel；網路只用於可選 enrichment（定義／翻譯／AI），
   並有本地快取。斷網時功能不減，只是少了英文定義。

## 4. 架構

```
src/word_flashcard_vocab_learner/
  __init__.py        # 公開 API：Card, Deck, ReviewSession；__version__
  models.py          # Card / Deck（JSON 存取、合併、統計）
  srs.py             # FSRS-lite 排程 + 留存率預測（純標準庫）
  scan/
    __init__.py      # compile_deck(), scan_text(), SUPPORTED_SUFFIXES
    cefr.py          # CEFR 字典載入（importlib.resources）、normalize、詞形還原
    extract.py       # txt/md/html 內建；pdf/docx/xlsx 走 extras；macOS OCR
    compile.py       # 句界切分、例句抽取、等級過濾、去重
  enrich/
    __init__.py      # 全部 lazy，import 時不連網
    dictionary.py    # Free Dictionary API + 快取
    llm.py           # requests 直呼 OpenAI 相容端點（不再依賴 openai）
    tts.py           # ElevenLabs（optional）
  cli.py             # argparse：demo / scan / review / stats / export / --version
  notebook.py        # HTML 卡片、牌組表格、留存率曲線（無 matplotlib）
  data/cefr.csv      # 打包資料
docs/
  index.md, quickstart.md, api.md, cli.md, faq.md
examples/
  demo.ipynb         # 演示用 notebook
tests/
```

依賴：

```toml
dependencies = []                       # 核心：零依賴
[project.optional-dependencies]
scan  = ["pdfplumber>=0.10", "python-docx>=1.1", "openpyxl>=3.1"]
ai    = []                              # 用 requests（stdlib 相容）
audio = ["elevenlabs>=1.0"]
dev   = ["pytest", "build", "twine"]
```

## 5. 資料模型

```python
@dataclass
class Card:
    word: str
    level: str                  # A1..C2
    pos: str | None = None
    definition: str | None = None
    example: str | None = None  # 來自使用者教材的那一句
    translation: str | None = None
    source: str | None = None
    # SRS 狀態
    stability: float = 0.0      # 天
    difficulty: float = 5.0     # 1..10
    reps: int = 0
    lapses: int = 0
    due: str | None = None      # ISO date
    last_review: str | None = None
```

`Deck` 是 `Card` 的有序集合，`save()/load()` 用 JSON（UTF-8、`ensure_ascii=False`），
`merge()` 依 `word.lower()` 去重並累加 `reps`。

## 6. 排程（FSRS-lite）

留存率曲線（FSRS-4.5 的形式，常數固定）：

```
R(t, S) = (1 + (19/81) * t / S) ^ (-0.5)
```

在目標留存率 0.9 時解出間隔：`I ≈ S`（乾淨的性質，測試可直接斷言）。

評分 1–4（Again / Hard / Good / Easy）：

- `Again`：`S' = max(0.1, S * 0.2)`，`D' = min(10, D + 0.8)`，`lapses += 1`
- `Hard`：`S' = S * 1.2`，`D' = min(10, D + 0.15)`
- `Good`：`S' = S * (1 + 0.9 * (11 - D) / 10)`，`D` 不變
- `Easy`：`S' = S * (1 + 1.3 * (11 - D) / 10)`，`D' = max(1, D - 0.3)`

新卡 `S = 1.0`、`D = 5.0`，首次複習後 `due = today + round(S')`。
一律用整數天，避免時區邊界問題。

## 7. 公開 API（評分表演示用）

```python
from word_flashcard_vocab_learner import Deck, ReviewSession

deck = Deck.from_document("lecture.pdf", min_level="B2")   # 需要 [scan]
review = ReviewSession(deck)      # notebook 內自動渲染成卡片
review.display()                  # 顯示當前卡
review.answer(3)                  # 1..4
deck.stats()                      # {'due_today': 12, 'retention_forecast': {...}}
deck.save("my_deck.json")
```

## 8. CLI

```
word-flashcard demo                 # 內建範例，30 秒跑完整流程（無需任何檔案／網路）
word-flashcard scan <file|dir>      # 掃描並輸出牌組 + CSV/Anki/Eudic
word-flashcard review [deck.json]   # 終端複習
word-flashcard stats [deck.json]    # 等級分佈、到期數、留存率
word-flashcard export --format anki
word-flashcard --version
```

`demo` 是為評分表演示而設：不讀使用者檔案、不連網、必定成功。

## 9. 掃描子套件

- CEFR 字典：`data/cefr.csv` 用 `importlib.resources` 讀，不依賴 cwd
- 詞形還原：規則式（`-s/-es/-ies/-ed/-ing/-ly`）＋ 字典已含屈折形式，**移除 nltk**
- 片語：2–4 字連詞比對
- 例句：以 `. ! ?` 切句，取第一個包含該詞的句子，截斷至 160 字元
- 檔案：`.txt/.md/.csv/.html` 內建；`.pdf/.docx/.xlsx` 需 `[scan]`，缺套件時給明確錯誤訊息
- OCR：保留 macOS Vision（`swiftc`），非 macOS 直接跳過並提示

## 10. 文件

- `README.md`：一句話定位、安裝、30 秒上手、API、CLI、限制、授權
- `docs/`：mkdocs-material，GitHub Pages 公開
- 所有公開函式有 docstring 與型別註解
- `examples/demo.ipynb`：可直接在 JupyterHub 跑的演示稿

## 11. 測試

- `tests/test_models.py`：Card 序列化、Deck merge 去重
- `tests/test_srs.py`：R(0)=1、R(S)≈0.9、四種評分單調性
- `tests/test_scan.py`：英文段落 → 只留 B2+、例句含該詞
- `tests/test_cli.py`：`--version`、`demo` 退出碼 0
- `tests/test_purity.py`：import 任何子模組都不產生網路／檔案副作用（用 monkeypatch 攔 requests）
- `tests/test_py39.py`：用 `ast.parse(feature_version=(3,9))` 掃全部原始碼

## 12. 發佈

1. `pyproject.toml` 版本 0.2.0、description 從 docstring 產生
2. `python -m build` → `dist/`
3. `twine upload dist/*`（需要 PyPI token；由組員執行，或設定 Trusted Publishing）
4. `git tag v0.2.0 && git push --tags`；GitHub Release 貼上 changelog
5. 在乾淨 venv 驗證：`pip install word-flashcard-vocab-learner==0.2.0` → `word-flashcard demo`

> 阻礙：目前 gh token 沒有 `workflow` scope，推送 `.github/workflows/` 會被拒。
> 解法：`gh auth refresh -s workflow`，或先不接 CI、手動上傳。

## 13. 五天排程

| 日 | 內容 | 產出 |
|---|---|---|
| 11/17 晚 | 設計定稿、repo 整理、models + srs + tests | 可 import 的核心 |
| 11/18 | 移植 scanner → `scan/`、`compile_deck`、例句抽取 | `Deck.from_document()` 可用 |
| 11/19 | CLI + notebook 渲染 + demo 資料 | `word-flashcard demo` 跑通 |
| 11/20 | README / docs / 測試補齊 / build / **PyPI 0.2.0** | 已發佈 |
| 11/21 | 緩衝、乾淨 venv 驗證、演示稿、分工排練 | 可演示 |
| 11/22 | 交件、簡報 | — |

## 14. 非目標

- 不做 GUI / web app
- 不做即時發音評分（列為 stretch，時間夠才加）
- 不做多使用者雲端同步
- 不保留模組層級的執行碼（`connectGenAI("Hello World!")` 之類）
- 不追求完整 FSRS 參數擬合，用固定常數的 lite 版

## 15. 分工

| 人 | 負責 | 演示段落 |
|---|---|---|
| Andy | `models` / `srs` / `notebook` / 整體架構 | 「一張卡是怎麼被排程的」 |
| Shing | `scan/` / `enrich/` / PyPI + CI | 「從講義到牌組」 |
| Kristy | `enrich/tts` / `docs/` / README / 測試 | 「發音與文件」 |

每人至少在自己負責的檔案留下 3 次有意義的 commit。
