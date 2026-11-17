# CEFR 字典資料來源

`cefr_words.csv` 由下列兩份開放資料合併、清理而成（拆開多寫法、去重、標註詞性與單詞/片語）：

1. **CEFR-J Vocabulary Profile (ver 1.5)**
   - 涵蓋 A1、A2、B1、B2
   - Compiled by Yukio Tono, Tokyo University of Foreign Studies (TUFS)
   - 取自 http://www.cefr-j.org/download.html
2. **Octanove Vocabulary Profile C1/C2 (ver 1.0)**
   - 涵蓋 C1、C2，由 Octanove Labs 製作
   - 授權：Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)

原始資料存放於 GitHub 專案
[openlanguageprofiles/olp-en-cefrj](https://github.com/openlanguageprofiles/olp-en-cefrj)：

- `cefrj-vocabulary-profile-1.5.csv`
- `octanove-vocabulary-profile-c1c2-1.0.csv`

## 授權

CEFR-J 詞彙與文法資料集可免費使用於研究與商業用途，惟須適當引用；版權屬東京外國語大學 Tono Laboratory。
Octanove Vocabulary Profile 依 CC BY-SA 4.0 授權。

引用方式（建議）：

> The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies.
> Octanove Vocabulary Profile C1/C2 (ver 1.0), Octanove Labs, CC BY-SA 4.0.

## 重新產生

```bash
python build_dictionary.py \
    data/cefrj-vocabulary-profile-1.5.csv \
    data/octanove-vocabulary-profile-c1c2-1.0.csv \
    -o data/cefr_words.csv
```

說明：當一個單詞同時出現在多個等級時，程式取「較低」等級作為主要等級
（符合 CEFR「該詞最早於此等級習得」的慣例），同時在 `all_levels` 保留全部等級。
