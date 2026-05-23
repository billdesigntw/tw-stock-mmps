# MMPS 整合說明
## 主力心態模擬預判系統 · tw-stock-evaluator 整合指南

---

## 📁 檔案說明

```
mmps/
├── mmps_module.py     ← 核心引擎（本檔）
└── INTEGRATION.md     ← 本說明文件
```

---

## ⚡ 三分鐘快速整合

### Step 1：放置模組

將 `mmps_module.py` 放在與你的 `tw-stock-evaluator` 同層目錄：

```
your_project/
├── tw_stock_evaluator.py   ← 你的主程式
├── mmps_module.py          ← 放這裡
└── dashboard_template.html
```

### Step 2：import 並填入訊號

```python
from mmps_module import MMPSAnalyzer, MMPSSignals

# 在你取得股票資料後，填入 7 項訊號
signals = MMPSSignals(
    stock_id    = "3017",
    stock_name  = "奇鋐科技",
    current_price = 2505,

    # 分點集中度：-1(分散) ~ +1(集中)
    concentration_score = 0.3,

    # 論壇情緒：+1(冷靜) ~ -1(瘋狂追高)
    sentiment_score = 0.4,

    # 量比（直接填原始數字，如 1.8 倍均量）
    volume_ratio = 0.7,

    # K線技術面：+1(多頭) ~ -1(空頭)
    kline_score = 0.4,

    # 法人方向：+1(買超) ~ -1(賣超)
    institutional_score = 0.2,

    # 宏觀環境：+1(利多) ~ -1(利空)
    macro_score = 0.7,

    # 基本面：+1(強) ~ -1(弱)
    fundamental_score = 0.9,

    # 股價位置 0~1（0=歷史低，1=歷史高）
    price_position = 0.70,

    # 補充說明（會顯示在報告底部）
    notes = "法說後利空出盡，外資仍在調節中"
)

# 執行分析
result = MMPSAnalyzer(signals).run()
```

### Step 3：取用輸出

```python
# 方式 A：HTML 區塊直接嵌入儀表板
html_block = result.html_block
# → 貼入你的 dashboard HTML 的適當位置即可

# 方式 B：文字摘要（放入報告）
print(result.summary)

# 方式 C：JSON 資料（API 或前端動態渲染）
import json
print(json.dumps(result.json_data, ensure_ascii=False, indent=2))

# 方式 D：個別取值
print(result.phase)              # "拉抬期"
print(result.phase_confidence)   # 0.62
print(result.recommendation)     # "持有 / 追強不追弱"
print(result.entry_zone)         # "2380–2505"
print(result.stop_loss)          # "跌破 2204"
```

---

## 🔌 嵌入 HTML 儀表板

在你的 `dashboard_template.html` 中找到要插入的位置，加入以下 Python 字串替換：

```python
# 在生成 HTML 的程式碼裡
mmps_result = MMPSAnalyzer(signals).run()

html_content = dashboard_template.replace(
    "<!-- MMPS_PLACEHOLDER -->",
    mmps_result.html_block
)
```

在 `dashboard_template.html` 中對應放置：

```html
<!-- 放在技術分析區塊之後、估值區塊之前 -->
<section id="mmps-section">
  <!-- MMPS_PLACEHOLDER -->
</section>
```

---

## 📊 訊號填寫參考表

| 訊號欄位 | 資料來源 | 填寫邏輯 |
|---------|---------|---------|
| `concentration_score` | 玩股網 / HiStock 分點進出 | 集中 +0.5~+1.0；分散 -0.5~-1.0 |
| `sentiment_score` | PTT、爆料同學會留言比 | 冷靜 +0.5；追高 -0.5；恐慌 -1.0 |
| `volume_ratio` | 任何報價工具 | 直接填比值（如 1.8、0.6） |
| `kline_score` | 技術圖 | 多頭排列 +0.6；空頭 -0.6；中性 0 |
| `institutional_score` | 三大法人表（TWSE） | 三大同買 +0.8；同賣 -0.8；分歧 0~0.3 |
| `macro_score` | 大盤 + 匯率 + 題材 | 順風 +0.7；逆風 -0.5；中性 0 |
| `fundamental_score` | 財報 + 法說展望 | EPS創高 +0.8；業績下修 -0.8 |
| `price_position` | 近60日位置 | 0=低點 0.5=中間 1.0=高點 |

### 快速評分捷徑

不確定如何填？用以下三段式：

```
+1.0 = 明確正面（有具體數據支持）
 0.0 = 不確定 / 未查到資料
-1.0 = 明確負面（有具體數據支持）
```

**最少只需 5 項訊號即可運行**，未知的填 0.0。

---

## 🔄 在 Claude 對話中的調用方式

當 Claude 執行 `tw-stock-evaluator` 分析時，可在系統提示（SKILL.md）中加入：

```
### MMPS 主力心態預判（必做步驟）

在完成籌碼面分析後，根據以下資料填入 MMPSSignals 並調用 MMPSAnalyzer：

- concentration_score：根據分點集中度判斷
- sentiment_score：根據論壇情緒判斷
- volume_ratio：從報價資料取得
- kline_score：根據技術分析結果判斷
- institutional_score：根據三大法人動向判斷
- macro_score：根據宏觀環境判斷
- fundamental_score：根據基本面評分判斷

將 result.html_block 插入儀表板 Section 13（MMPS 主力預判）。
```

---

## 📤 雲端調用架構（未來擴充）

若要讓 MMPS 變成可遠端調用的 API：

```
GitHub repo → Actions 定時更新訊號 → 暴露 JSON endpoint
tw-stock-evaluator → fetch(mmps_api_url) → 取得最新預判
```

**現階段建議流程：**
1. 本地執行 `mmps_module.py`，取得 `result.html_block`
2. 手動貼入儀表板模板
3. 推送更新的儀表板到 GitHub Pages

**未來 Phase 2：**
```python
# 自動從 GitHub 抓取最新訊號 JSON
import urllib.request, json

url = "https://raw.githubusercontent.com/billdesigntw/tw-stock-mmps/main/signals/{stock_id}.json"
with urllib.request.urlopen(url.format(stock_id="3017")) as r:
    signals_data = json.loads(r.read())

signals = MMPSSignals(**signals_data)
result = MMPSAnalyzer(signals).run()
```

---

## 🔢 輸出完整結構

```python
result.phase                  # str: "吸貨期" / "洗盤期" / "拉抬期" / "出貨期"
result.phase_confidence       # float: 0.0–1.0
result.phase_probabilities    # dict: { "吸貨期": 0.32, "拉抬期": 0.31, ... }
result.next_step_probabilities # list: [{ label, prob, dir, detail }, ...]
result.signal_scores          # dict: 正規化後的訊號值
result.dimension_scores       # dict: { "心理面": 6.8, "技術面": 5.4, ... }
result.fingerprint_match      # dict: 各週期指紋符合度
result.recommendation         # str: 操作建議
result.entry_zone             # str: 建議進場區間
result.stop_loss              # str: 停損參考
result.trigger_up             # list: 加碼觸發條件
result.trigger_down           # list: 停損觸發條件
result.summary                # str: 純文字摘要
result.html_block             # str: 完整 HTML（直接嵌入用）
result.json_data              # dict: 完整 JSON（API / 前端用）
```

---

## 🛠️ 自訂觸發條件

系統預設給通用的觸發條件，可在調用時覆蓋：

```python
result = MMPSAnalyzer(signals).run()

# 覆蓋觸發條件
result.trigger_up = [
    "外資轉買超連 3 日",
    "Rubin 設計疑雲正式澄清",
    "Q2 EPS 超預期",
]
result.trigger_down = [
    "毛利率再度低於 4.5%",
    "外資連賣 5 日以上",
    "健策跌停拖累族群",
]

# 重新生成 HTML（含自訂觸發條件）
# 注意：需重新 build HTML，或手動替換觸發條件部分
```

---

## ⚠️ 免責聲明

MMPS 為行為金融學研究工具，所有概率為模型估算值，不代表實際主力決策，不構成投資建議。

---

*MMPS v1.0 · 2026/05 · billdesigntw/tw-stock-mmps*
