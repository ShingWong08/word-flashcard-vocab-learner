# 英文文件 CEFR 單詞等級掃描工具

**中文** | [English](README.en.md)

掃描 PDF、Word、Excel、圖片、純文字等檔案，分析每個英文單詞的 CEFR 等級（A1–C2），
並自動把 **B2 到 C2** 的高級單詞／片語整理成單詞簿，附英文定義與出處例句。

## 功能

- 支援 PDF（.pdf）、Word（.docx）、Excel（.xlsx）、圖片（.png/.jpg/.tiff）與純文字（.txt/.csv/.md/.html）
- 支援單一檔案或多個檔案／整個資料夾（遞迴掃描）
- 掃描圖片 PDF：自動偵測「沒有文字層」的 PDF，改用 Apple Vision OCR 認字（macOS）
- 內建 CEFR 字典（A1–C2，約 1 萬筆詞條，來源見 `data/SOURCES.md`）
- 詞形還原（run/runs/ran → run）與英文定義（WordNet，可離線）
- 可選翻譯：把單詞翻譯成指定語言（繁中、簡中、日、韓、西、法等），只翻單詞本身
- 匯出多種格式，方便匯入字典或背單詞 App

## 安裝

```bash
cd vocabulary_scanner
python3 -m pip install -r requirements.txt
python3 -m nltk.downloader wordnet omw-1.4   # 首次執行需要，用於英文定義與詞形還原
```

> 若無法安裝 nltk 或下載 WordNet，程式仍可執行，只是會跳過「詞形還原」與「英文定義」，
> 改用單詞原形比對（CEFR-J 字典本身已含大量屈折形式，仍有相當涵蓋率）。

### OCR（macOS，選用）

OCR 使用 Apple 內建的 Vision 框架，不需要另外安裝 Tesseract。啟用條件：

- macOS 需有 **Xcode 命令列工具**（`swiftc` 可用）。終端機執行 `xcode-select --install` 即可安裝。
- 首次用到 OCR 時，程式會自動把 `ocr/vision_ocr.swift` 編譯成 `build/vision_ocr`。

OCR 只在「PDF 沒有文字層」時才會觸發（`--ocr auto`，預設）；原生文字 PDF 完全不經過 OCR，速度不受影響。

### 翻譯（選用）

翻譯使用 Google 翻譯（`deep-translator`），需要網路連線；翻譯結果會快取在
`data/translations/`，之後同樣的單詞離線也能用，不會重複連線。

## 使用

### 最省事的方法：完全不用手打路徑

路徑有空白時（例如 `Group 6_TAM ... Final Version.docx`）必須加引號，手動輸入很容易少一個引號就報錯。
最簡單的做法是讓終端機自己幫你貼：

1. 開 Terminal，先輸入 `python3 vocab_scanner.py`，**結尾留一個空格**
2. 從 Finder 把檔案（或整個資料夾）拖進 Terminal 視窗 → 路徑會自動貼上並加好引號
3. 按 Enter

指令在正確的資料夾（`vocabulary_scanner/`）下執行即可。要拖檔案進去，先開另一個 Finder 視窗指到檔案位置。

> 所有參數都是選填的。不加 `--out-dir` 時結果一律寫到 `output/`；加它只是換一個輸出資料夾，
> 避免覆蓋上一次的結果，例如 `--out-dir output/essay`。

### 完整指令範例

```bash
# 掃描整個資料夾
python3 vocab_scanner.py sample/

# 掃描多個檔案
python3 vocab_scanner.py report.pdf notes.docx data.xlsx

# 合併進既有單詞簿（累加次數、保留來源）
python3 vocab_scanner.py new_docs/ --merge output/vocabulary_book.csv

# 只查詢某個單詞的等級
python3 vocab_scanner.py --lookup ambiguous

# 掃描並把單詞翻譯成繁體中文（只翻單詞，不翻定義）
python3 vocab_scanner.py sample/ --translate zh-TW

# 支援語言名稱或代碼，例如：zh-CN（簡中）、ja（日）、ko（韓）、es（西）、fr（法）
python3 vocab_scanner.py sample/ --translate 日文

# 強制所有 PDF 都用 OCR（通常不需要）
python3 vocab_scanner.py scans/ --ocr force

# 完全關閉 OCR
python3 vocab_scanner.py scans/ --ocr off
```

## 參數

| 參數 | 說明 | 預設 |
|------|------|------|
| `inputs` | 檔案或資料夾（可多個） | 無 |
| `--out-dir` | 輸出資料夾 | `output/` |
| `--min-level` | 單詞簿最低等級 | `B2` |
| `--max-level` | 單詞簿最高等級 | `C2` |
| `--merge` | 合併進既有 `vocabulary_book.csv` | 無 |
| `--sort` | 排序方式 `level`（依等級）或 `count`（依次數） | `level` |
| `--top` | 報告中未知單詞顯示數量 | `30` |
| `--no-definitions` | 不查詢 WordNet 英文定義 | 無 |
| `--lookup` | 查詢單詞等級後離開 | 無 |
| `--ocr` | OCR 模式：`auto`＝沒有文字層才 OCR、`force`＝PDF 一律 OCR、`off`＝關閉 | `auto` |
| `--ocr-dpi` | OCR 時 PDF 渲染解析度 | `200` |
| `--translate` | 把單詞翻譯成指定語言（`zh-TW`、`zh-CN`、`ja`、`ko`、`es`、`fr`…；只翻單詞） | 無 |

## 輸出（預設在 `output/`）

| 檔案 | 用途 |
|------|------|
| `vocabulary_book.xlsx` | Excel 單詞簿（含「翻譯」欄與「等級統計」分頁） |
| `vocabulary_book.csv` | CSV 單詞簿，可作為 `--merge` 的合併檔 |
| `vocabulary_anki.tsv` | Anki 匯入檔（單詞／定義／例句／等級） |
| `vocabulary_eudic.txt` | 欧路词典、有道等生詞本匯入檔（每行一詞） |
| `vocabulary_book.json` | JSON 格式 |
| `analysis_report.txt` | 完整分析報告（各等級分布 + 高級單詞清單） |

## 匯入字典／背單詞 App

- **Anki**：檔案 → 匯入 → 選擇 `vocabulary_anki.tsv`，分隔符選「Tab」，
  欄位對應「單詞、定義、例句、等級、詞性、翻譯」。
- **欧路词典（Eudic）**：學習 → 生詞本 → 匯入 → 選 `vocabulary_eudic.txt`（每行一個單詞）。
- **有道／其他**：多數 App 支援匯入每行一個單詞的 `.txt`，用 `vocabulary_eudic.txt` 即可。

## 等級判定規則

- 單詞先以小寫、去重音、原形比對；比不到時用 WordNet 做詞形還原後再比對。
- 一個單詞若同時出現在多個等級，以「較低」等級為主（CEFR 慣例），並在 `all_levels` 保留全部等級。
- 片語（如 `climate change`）會以 2–4 字連詞比對，與單詞分開列在單詞簿中。

## 注意事項

- 舊版 Word `.doc` 與 Excel `.xls` 不直接支援，請先用 Word/Excel 另存成 `.docx`／`.xlsx`。
- 掃描圖片 PDF 會自動用 OCR；解析度越高（`--ocr-dpi`）越準但越慢，頁數多時請耐心等待。
- 翻譯需連上網路；首次翻譯一批新單詞會較慢，之後走快取（`data/translations/`）就快了。
- CEFR 等級為「近似」參考，同一個字在不同語境、不同詞性下等級可能不同。
