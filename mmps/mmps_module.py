"""
╔══════════════════════════════════════════════════════════════════╗
║   MMPS — Market Maker Psychology Simulation System              ║
║   主力心態模擬預判系統 v1.0                                        ║
║                                                                  ║
║   設計用途：作為獨立模組被 tw-stock-evaluator 調用                  ║
║   輸入：7項可觀測訊號（最少5項）                                    ║
║   輸出：主力週期判斷 + 下一步概率 + HTML區塊（可嵌入儀表板）           ║
║                                                                  ║
║   整合方式：                                                       ║
║     from mmps_module import MMPSAnalyzer                         ║
║     result = MMPSAnalyzer(signals).run()                         ║
║     html_block = result['html_block']   # 嵌入儀表板               ║
║     summary = result['summary']         # 文字摘要                  ║
╚══════════════════════════════════════════════════════════════════╝

依賴套件：無（純 Python 標準庫）
Python 版本：3.8+
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
import math


# ─────────────────────────────────────────────
# 資料結構
# ─────────────────────────────────────────────

@dataclass
class MMPSSignals:
    """
    7 項輸入訊號。
    分數範圍皆為 -1.0（極度負面）~ +1.0（極度正面），0 = 中性/未知。
    可由外部程式根據實際資料填入，未知填 0.0。

    使用範例：
        signals = MMPSSignals(
            concentration_score=0.6,    # 分點集中度上升
            volume_ratio=1.8,           # 量比（今日/5日均量）
            kline_score=0.4,            # K線技術面
            institutional_score=0.5,    # 法人動向
            sentiment_score=-0.2,       # 論壇情緒
            macro_score=0.7,            # 宏觀環境
            fundamental_score=0.8,      # 基本面
        )
    """

    # ── 維度一：金融心理 ──────────────────────────
    sentiment_score: float = 0.0
    """
    論壇情緒溫度
    +1.0 = 散戶冷靜/不追高（有利主力吸貨）
    -1.0 = 散戶瘋狂追高（過熱，主力易出貨）
    0.0  = 中性/未知
    來源：PTT、爆料同學會、Dcard 留言比例
    """

    concentration_score: float = 0.0
    """
    籌碼集中度變化
    +1.0 = 分點快速集中（主力積極吸貨）
    -1.0 = 分點明顯分散（主力出貨中）
    0.0  = 無明顯變化/未知
    來源：玩股網、HiStock 分點進出
    """

    # ── 維度二：技術操作 ──────────────────────────
    volume_ratio: float = 1.0
    """
    量比 = 今日成交量 / 5日均量
    > 2.0 = 爆量
    1.0   = 均量
    < 0.5 = 量縮
    來源：任何報價工具
    注意：此欄位是原始比值，系統內部會自動轉換
    """

    kline_score: float = 0.0
    """
    K線技術面綜合評分
    +1.0 = 均線多頭排列 + 突破 + 收長紅
    -1.0 = 均線空頭排列 + 跌破 + 收長黑
    0.0  = 中性整理/未知
    來源：技術圖分析
    """

    # ── 維度三：法人籌碼（台股核心訊號）──────────────
    institutional_score: float = 0.0
    """
    三大法人方向強度
    +1.0 = 三大法人同向大量買超（連買3日以上）
    -1.0 = 三大法人同向大量賣超
    0.0  = 分歧或持平/未知
    來源：台灣證交所三大法人表
    """

    # ── 維度四：宏觀環境 ──────────────────────────
    macro_score: float = 0.0
    """
    宏觀環境綜合評分
    +1.0 = 大盤強勢 + 台幣升值 + 外資匯入 + 產業題材熱
    -1.0 = 大盤弱勢 + 台幣貶值 + 外資匯出 + 宏觀逆風
    0.0  = 中性/未知
    """

    # ── 維度五：基本面（錨定主力長期意願）───────────
    fundamental_score: float = 0.0
    """
    基本面強度
    +1.0 = EPS 創高 + 營收爆發 + 法說展望樂觀
    -1.0 = 業績下修 + 毛利惡化 + 法說展望保守
    0.0  = 中性/未知
    """

    # ── 補充資訊（可選）──────────────────────────
    stock_id: str = ""
    stock_name: str = ""
    current_price: float = 0.0
    price_position: float = 0.5
    """
    股價相對近60日位置
    1.0 = 歷史高點附近
    0.0 = 歷史低點附近
    0.5 = 中間位置（預設）
    """

    notes: str = ""
    """自由填寫的補充說明，會顯示在報告備注欄"""


@dataclass
class MMPSResult:
    """MMPS 分析結果"""
    phase: str                          # 當前週期名稱
    phase_confidence: float             # 週期判斷信心度 0-1
    phase_probabilities: dict           # 四大週期各自概率
    next_step_probabilities: list       # 下一步手法概率列表
    signal_scores: dict                 # 各訊號評分
    dimension_scores: dict              # 四維評分
    fingerprint_match: dict             # 指紋符合度
    recommendation: str                 # 操作建議
    entry_zone: str                     # 建議進場區間
    stop_loss: str                      # 停損參考
    trigger_up: list                    # 加碼觸發條件
    trigger_down: list                  # 停損觸發條件
    summary: str                        # 文字摘要（可直接嵌入報告）
    html_block: str                     # HTML 區塊（可嵌入儀表板）
    json_data: dict                     # 完整 JSON 資料（供前端使用）


# ─────────────────────────────────────────────
# 核心引擎
# ─────────────────────────────────────────────

class MMPSAnalyzer:
    """
    主力心態模擬預判引擎

    四大週期：
        吸貨期 → 洗盤期 → 拉抬期 → 出貨期
              ↑________________________|

    貝式概率公式：
        P(週期) = Σ(訊號權重 × 訊號強度 × 週期係數) / 正規化因子
    """

    # 各週期的訊號偏好矩陣
    # 格式：{ 週期名: { 訊號: 期望值方向 } }
    # +1 = 此訊號偏正值時支持該週期，-1 = 偏負值時支持
    PHASE_MATRIX = {
        "吸貨期": {
            "concentration_score": +1.2,   # 分點集中 → 強烈吸貨信號
            "sentiment_score":     +0.8,    # 散戶冷淡 → 有利低調吸貨
            "volume_ratio_norm":   -0.5,    # 量縮 → 悄悄吸貨
            "institutional_score": +0.6,    # 法人小量買 → 配合吸貨
            "kline_score":         -0.3,    # 低檔盤整 → 正常
            "macro_score":         +0.3,
            "fundamental_score":   +0.5,    # 基本面好才值得吸
            "price_position_neg":  +0.8,    # 低價位 → 吸貨機會
        },
        "洗盤期": {
            "concentration_score": +0.6,    # 集中度不降（假出貨）
            "sentiment_score":     -0.8,    # 散戶恐慌 → 洗盤目的達成
            "volume_ratio_norm":   +0.5,    # 量放大 → 製造恐慌
            "institutional_score": -0.7,    # 法人賣超（假動作）
            "kline_score":         -0.9,    # 破線跌 → 洗盤手法
            "macro_score":         +0.0,
            "fundamental_score":   +0.3,
            "price_position_neg":  +0.4,
        },
        "拉抬期": {
            "concentration_score": +0.5,
            "sentiment_score":     -0.3,    # 散戶開始追 → 拉抬後段
            "volume_ratio_norm":   +1.0,    # 量爆 → 強烈拉抬信號
            "institutional_score": +1.2,    # 法人同向大買 → 核心信號
            "kline_score":         +1.0,    # 均線多頭 + 突破
            "macro_score":         +0.7,    # 大盤配合
            "fundamental_score":   +0.6,
            "price_position_neg":  -0.3,    # 中高位 → 拉抬中段
        },
        "出貨期": {
            "concentration_score": -1.0,    # 分點分散 → 出貨信號
            "sentiment_score":     -0.5,    # 散戶瘋狂 → 利多出盡
            "volume_ratio_norm":   +0.6,    # 量大 → 高位放量
            "institutional_score": -1.0,    # 法人賣超 → 出貨確認
            "kline_score":         +0.2,    # 股價仍在高位
            "macro_score":         +0.3,
            "fundamental_score":   +0.2,
            "price_position_neg":  -1.0,    # 高位 → 出貨環境
        },
    }

    # 各訊號的全局權重
    SIGNAL_WEIGHTS = {
        "concentration_score": 0.20,
        "sentiment_score":     0.12,
        "volume_ratio_norm":   0.15,
        "institutional_score": 0.22,
        "kline_score":         0.12,
        "macro_score":         0.10,
        "fundamental_score":   0.09,
        "price_position_neg":  0.00,  # 僅用於週期矩陣，不單獨計分
    }

    PHASE_COLORS = {
        "吸貨期": "#4080e8",
        "洗盤期": "#e84040",
        "拉抬期": "#30c080",
        "出貨期": "#e8a020",
    }

    def __init__(self, signals: MMPSSignals):
        self.s = signals
        self._preprocess()

    def _preprocess(self):
        """前處理：正規化量比、價格位置"""
        vr = self.s.volume_ratio
        # 量比 → [-1, +1]：>2 為爆量(+1)，<0.5 為量縮(-0.8)，1.0 為均量(0)
        if vr >= 2.0:
            self._volume_norm = min(1.0, (vr - 1.0) / 2.0)
        elif vr >= 1.0:
            self._volume_norm = (vr - 1.0) / 1.0 * 0.5
        else:
            self._volume_norm = -(1.0 - vr) * 0.8

        # 價格位置 → 出貨期用負值（高位 = 支持出貨）
        self._price_pos_neg = -(self.s.price_position - 0.5) * 2.0

    def _get_signal_vector(self) -> dict:
        return {
            "concentration_score": self.s.concentration_score,
            "sentiment_score":     self.s.sentiment_score,
            "volume_ratio_norm":   self._volume_norm,
            "institutional_score": self.s.institutional_score,
            "kline_score":         self.s.kline_score,
            "macro_score":         self.s.macro_score,
            "fundamental_score":   self.s.fundamental_score,
            "price_position_neg":  self._price_pos_neg,
        }

    def _compute_phase_scores(self) -> dict:
        """計算四大週期原始分數"""
        sv = self._get_signal_vector()
        scores = {}
        for phase, matrix in self.PHASE_MATRIX.items():
            score = 0.0
            for sig, direction in matrix.items():
                val = sv.get(sig, 0.0)
                score += val * direction * self.SIGNAL_WEIGHTS.get(sig, 0.1)
            scores[phase] = score
        return scores

    def _softmax(self, scores: dict) -> dict:
        """Softmax 正規化為概率"""
        # 先平移讓最小值 >= 0
        min_v = min(scores.values())
        shifted = {k: v - min_v + 0.1 for k, v in scores.items()}
        # Softmax with temperature=2
        exp_v = {k: math.exp(v * 2) for k, v in shifted.items()}
        total = sum(exp_v.values())
        return {k: round(v / total, 3) for k, v in exp_v.items()}

    def _determine_phase(self, probs: dict) -> tuple[str, float]:
        """判斷最可能的週期"""
        best = max(probs, key=probs.get)
        return best, probs[best]

    def _compute_dimension_scores(self) -> dict:
        """四維評分 0-10"""
        s = self.s
        psychology = round(((s.sentiment_score + s.concentration_score) / 2 + 1) * 5, 1)
        technical  = round(((self._volume_norm + s.kline_score) / 2 + 1) * 5, 1)
        macro      = round((s.macro_score + 1) * 5, 1)
        regulatory = 8.0  # 固定基準，使用者可覆蓋
        return {
            "心理面": max(0, min(10, psychology)),
            "技術面": max(0, min(10, technical)),
            "宏觀面": max(0, min(10, macro)),
            "法規面": regulatory,
        }

    def _compute_next_steps(self, phase: str, probs: dict) -> list:
        """
        根據當前週期生成下一步手法概率清單
        返回：[{ label, prob, direction, detail }, ...]
        """
        templates = {
            "吸貨期": [
                {"label": "繼續低調吸貨整理",      "base": 0.40, "dir": "↔", "detail": "維持量縮橫盤，等待更多籌碼集中"},
                {"label": "假跌破洗盤後拉抬",      "base": 0.35, "dir": "↓↑","detail": "跌破支撐嚇走浮額後快速回收"},
                {"label": "直接帶量突破拉抬",      "base": 0.18, "dir": "↑", "detail": "等待大盤配合，一根長紅啟動"},
                {"label": "放棄操盤觀望",          "base": 0.07, "dir": "↓", "detail": "若宏觀轉空，主力可能暫停佈局"},
            ],
            "洗盤期": [
                {"label": "快速V轉進入拉抬期",     "base": 0.45, "dir": "↓↑","detail": "洗盤完成後快速回收，均線持多頭"},
                {"label": "繼續深洗跌破更低支撐",  "base": 0.30, "dir": "↓", "detail": "繼續清洗意志不堅的持股者"},
                {"label": "緩慢盤整後伺機拉抬",    "base": 0.20, "dir": "↔", "detail": "橫盤震盪，等待時機"},
                {"label": "真實出貨非洗盤",        "base": 0.05, "dir": "↓", "detail": "若基本面惡化，可能真的出貨"},
            ],
            "拉抬期": [
                {"label": "持續帶量攻高",          "base": 0.42, "dir": "↑", "detail": "法人同向買超配合，均線持多頭排列"},
                {"label": "震盪洗盤後再攻",        "base": 0.28, "dir": "↔↑","detail": "短線獲利了結洗盤後繼續拉高"},
                {"label": "利多出盡開始出貨",      "base": 0.20, "dir": "↑↓","detail": "接近目標價，主力邊拉邊出"},
                {"label": "急跌回測支撐",          "base": 0.10, "dir": "↓", "detail": "外部利空或主力假動作測試支撐"},
            ],
            "出貨期": [
                {"label": "高檔震盪消化籌碼",      "base": 0.38, "dir": "↔", "detail": "主力溫水煮青蛙，緩慢出貨"},
                {"label": "急拉出貨後急跌",        "base": 0.30, "dir": "↑↓","detail": "利用短線刺激讓散戶追高，趁機出清"},
                {"label": "築底重新吸貨",          "base": 0.22, "dir": "↓↑","detail": "若股價跌至新低，主力可能重新佈局"},
                {"label": "持續崩跌無人接手",      "base": 0.10, "dir": "↓", "detail": "基本面惡化或主力完全離場"},
            ],
        }

        steps = templates.get(phase, templates["拉抬期"])

        # 根據訊號微調概率
        s = self.s
        adjusted = []
        for step in steps:
            p = step["base"]
            # 根據法人方向微調
            if "拉抬" in step["label"] or "攻高" in step["label"]:
                p += s.institutional_score * 0.08
            if "出貨" in step["label"] or "崩跌" in step["label"]:
                p -= s.institutional_score * 0.05
                p -= s.fundamental_score * 0.03
            p = max(0.02, min(0.80, p))
            adjusted.append({**step, "prob": p})

        # 正規化
        total = sum(x["prob"] for x in adjusted)
        for x in adjusted:
            x["prob"] = round(x["prob"] / total, 3)

        return sorted(adjusted, key=lambda x: x["prob"], reverse=True)

    def _fingerprint_match(self, phase: str) -> dict:
        """計算當前訊號與各週期指紋的符合度"""
        sv = self._get_signal_vector()
        results = {}
        for p, matrix in self.PHASE_MATRIX.items():
            matches = 0
            total = 0
            for sig, direction in matrix.items():
                val = sv.get(sig, 0.0)
                if abs(direction) > 0.4:  # 只計算高權重訊號
                    total += 1
                    if val * direction > 0.15:  # 方向一致
                        matches += 1
            results[p] = round(matches / max(total, 1), 2)
        return results

    def _recommendation(self, phase: str, probs: dict) -> tuple[str, str, str]:
        """生成操作建議"""
        s = self.s
        price = s.current_price
        rec_map = {
            "吸貨期": ("逢低分批建倉", f"{price*0.95:.0f}–{price:.0f}", f"跌破 {price*0.88:.0f}"),
            "洗盤期": ("觀望等待止跌信號", f"{price*0.92:.0f}–{price*0.97:.0f}", f"跌破 {price*0.85:.0f}"),
            "拉抬期": ("持有 / 追強不追弱", f"{price:.0f}–{price*1.03:.0f}", f"跌破 {price*0.93:.0f}"),
            "出貨期": ("減碼 / 謹慎觀望", f"{price*0.88:.0f}–{price*0.95:.0f}", f"跌破 {price*0.85:.0f}"),
        }
        return rec_map.get(phase, ("觀望", "N/A", "N/A"))

    def _build_summary(self, phase: str, confidence: float,
                       next_steps: list, dim: dict) -> str:
        """生成純文字摘要"""
        top = next_steps[0]
        lines = [
            f"【MMPS 主力心態預判】{self.s.stock_id} {self.s.stock_name}",
            f"當前週期：{phase}（信心度 {confidence:.0%}）",
            f"下一步最高概率：{top['label']}（{top['prob']:.0%}）— {top['detail']}",
            f"四維評分 | 心理:{dim['心理面']:.1f} 技術:{dim['技術面']:.1f} 宏觀:{dim['宏觀面']:.1f} 法規:{dim['法規面']:.1f}",
        ]
        if self.s.notes:
            lines.append(f"補充：{self.s.notes}")
        return "\n".join(lines)

    def _build_html_block(self, phase: str, confidence: float,
                          phase_probs: dict, next_steps: list,
                          dim: dict, fingerprint: dict,
                          rec: str, entry: str, stop: str,
                          trigger_up: list, trigger_down: list) -> str:
        """
        生成可直接嵌入 tw-stock-evaluator 儀表板的 HTML 區塊。
        完全獨立的 CSS（用 mmps- 前綴避免衝突），無外部依賴。
        """
        color = self.PHASE_COLORS.get(phase, "#888")
        top_next = next_steps[0]

        # 概率條 HTML
        prob_bars = ""
        phase_order = ["拉抬期", "吸貨期", "洗盤期", "出貨期"]
        phase_colors_list = ["#30c080", "#4080e8", "#e84040", "#e8a020"]
        for ph, col in zip(phase_order, phase_colors_list):
            pct = int(phase_probs.get(ph, 0) * 100)
            active = "font-weight:600;color:#fff;" if ph == phase else ""
            prob_bars += f"""
            <div style="display:grid;grid-template-columns:70px 1fr 36px;align-items:center;gap:6px;margin-bottom:7px;">
              <span style="font-size:11px;{active}">{ph}</span>
              <div style="height:5px;background:#1e2630;border-radius:3px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{col};border-radius:3px;"></div>
              </div>
              <span style="font-size:10px;color:#7a8898;text-align:right;font-family:monospace;">{pct}%</span>
            </div>"""

        # 下一步手法 HTML
        next_html = ""
        for i, ns in enumerate(next_steps[:4]):
            p = int(ns["prob"] * 100)
            border = f"border-color:{color};background:rgba(0,0,0,0.1);" if i == 0 else ""
            next_html += f"""
            <div style="background:#0f1218;border:1px solid #1e2630;{border}border-radius:5px;padding:8px 10px;display:grid;grid-template-columns:1fr auto;align-items:center;gap:6px;margin-bottom:6px;">
              <div>
                <div style="font-size:12px;color:#c8d0dc;">{ns['label']}</div>
                <div style="font-size:10px;color:#4a5568;margin-top:2px;">{ns['detail']}</div>
              </div>
              <div style="text-align:right;">
                <div style="font-family:monospace;font-size:15px;font-weight:600;color:{'#30c080' if p>35 else '#e8a020' if p>20 else '#7a8898'};">{p}%</div>
                <div style="font-size:9px;color:#4a5568;">{ns['dir']}</div>
              </div>
            </div>"""

        # 四維評分 HTML
        dim_html = ""
        for name, score in dim.items():
            col = "#30c080" if score >= 7 else "#e8a020" if score >= 5 else "#e84040"
            dim_html += f"""
            <div style="background:#0f1218;border:1px solid #1e2630;border-radius:5px;padding:10px;">
              <div style="font-size:10px;color:#4a5568;margin-bottom:4px;">{name}</div>
              <div style="font-family:monospace;font-size:18px;font-weight:600;color:{col};">{score:.1f}<span style="font-size:10px;color:#4a5568;">/10</span></div>
            </div>"""

        # 觸發條件 HTML
        up_items = "".join(f'<li style="margin-bottom:3px;color:#30c080;">✓ {x}</li>' for x in trigger_up)
        dn_items = "".join(f'<li style="margin-bottom:3px;color:#e84040;">✗ {x}</li>' for x in trigger_down)

        html = f"""
<!-- ══ MMPS 主力心態預判區塊 ══ -->
<div id="mmps-block" style="
  background:#0a0c10;
  border:1px solid #1e2630;
  border-left:3px solid {color};
  border-radius:8px;
  padding:16px;
  margin:16px 0;
  font-family:'Noto Sans TC',sans-serif;
">
  <!-- 標題列 -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
    <div>
      <div style="font-family:monospace;font-size:9px;color:{color};letter-spacing:2px;margin-bottom:3px;">◈ MMPS · 主力心態模擬預判</div>
      <div style="font-size:16px;font-weight:700;color:#fff;">
        {phase}
        <span style="font-size:11px;font-weight:400;color:#4a5568;margin-left:6px;">信心度 {confidence:.0%}</span>
      </div>
    </div>
    <div style="background:{color}22;border:1px solid {color}55;border-radius:6px;padding:6px 12px;text-align:center;">
      <div style="font-size:9px;color:{color};margin-bottom:2px;">下一步最高概率</div>
      <div style="font-size:13px;font-weight:600;color:#fff;">{top_next['prob']:.0%}</div>
      <div style="font-size:10px;color:#7a8898;">{top_next['label'][:10]}</div>
    </div>
  </div>

  <!-- 週期概率 -->
  <div style="margin-bottom:14px;">
    <div style="font-size:9px;color:#4a5568;letter-spacing:1px;margin-bottom:8px;font-family:monospace;">週期概率矩陣</div>
    {prob_bars}
  </div>

  <!-- 分隔 -->
  <div style="height:1px;background:#1e2630;margin-bottom:14px;"></div>

  <!-- 下一步手法 -->
  <div style="margin-bottom:14px;">
    <div style="font-size:9px;color:#4a5568;letter-spacing:1px;margin-bottom:8px;font-family:monospace;">▶ 下一步主力手法概率</div>
    {next_html}
  </div>

  <!-- 四維評分 -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px;">
    {dim_html}
  </div>

  <!-- 操作建議 -->
  <div style="background:#0f1218;border:1px solid {color}44;border-radius:6px;padding:12px;margin-bottom:12px;">
    <div style="font-size:9px;color:{color};letter-spacing:1px;margin-bottom:8px;font-family:monospace;">📌 操作建議</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
      <div><div style="font-size:9px;color:#4a5568;margin-bottom:2px;">建議</div><div style="font-size:13px;font-weight:600;color:#fff;">{rec}</div></div>
      <div><div style="font-size:9px;color:#4a5568;margin-bottom:2px;">理想進場</div><div style="font-size:13px;font-weight:600;color:#30c080;">{entry}</div></div>
      <div><div style="font-size:9px;color:#4a5568;margin-bottom:2px;">停損參考</div><div style="font-size:13px;font-weight:600;color:#e84040;">{stop}</div></div>
      <div><div style="font-size:9px;color:#4a5568;margin-bottom:2px;">現價</div><div style="font-size:13px;font-weight:600;color:#c8d0dc;">NT${self.s.current_price:.0f}</div></div>
    </div>
  </div>

  <!-- 觸發條件 -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    <div style="background:#0f1218;border:1px solid #1e2630;border-radius:5px;padding:10px;">
      <div style="font-size:9px;color:#30c080;margin-bottom:6px;font-family:monospace;">加碼觸發條件</div>
      <ul style="list-style:none;font-size:11px;color:#4a5568;">{up_items}</ul>
    </div>
    <div style="background:#0f1218;border:1px solid #1e2630;border-radius:5px;padding:10px;">
      <div style="font-size:9px;color:#e84040;margin-bottom:6px;font-family:monospace;">停損觸發條件</div>
      <ul style="list-style:none;font-size:11px;color:#4a5568;">{dn_items}</ul>
    </div>
  </div>

  <!-- 資料說明 -->
  <div style="margin-top:10px;font-size:9px;color:#3a4858;line-height:1.5;">
    MMPS v1.0 · 基於行為金融學框架 · 概率為估算值，不構成投資建議
    {"· 補充：" + self.s.notes if self.s.notes else ""}
  </div>
</div>
<!-- ══ /MMPS ══ -->
"""
        return html

    def run(self) -> MMPSResult:
        """執行完整 MMPS 分析，返回 MMPSResult"""
        # 1. 計算週期概率
        raw_scores = self._compute_phase_scores()
        phase_probs = self._softmax(raw_scores)
        phase, confidence = self._determine_phase(phase_probs)

        # 2. 下一步手法
        next_steps = self._compute_next_steps(phase, phase_probs)

        # 3. 四維評分
        dim_scores = self._compute_dimension_scores()

        # 4. 指紋比對
        fingerprint = self._fingerprint_match(phase)

        # 5. 操作建議
        rec, entry, stop = self._recommendation(phase, phase_probs)

        # 6. 觸發條件（可由使用者覆蓋，這裡給通用版）
        trigger_up = [
            "外資轉為連買 3 日以上",
            "分點集中度明顯上升",
            "量能放大突破近期高點",
        ]
        trigger_down = [
            "法人連續賣超 5 日以上",
            "跌破關鍵支撐且量縮",
            "基本面重大負面消息",
        ]

        # 7. 文字摘要
        summary = self._build_summary(phase, confidence, next_steps, dim_scores)

        # 8. HTML 區塊
        html_block = self._build_html_block(
            phase, confidence, phase_probs, next_steps,
            dim_scores, fingerprint, rec, entry, stop,
            trigger_up, trigger_down
        )

        # 9. JSON 資料（供前端/API使用）
        json_data = {
            "stock_id": self.s.stock_id,
            "stock_name": self.s.stock_name,
            "current_price": self.s.current_price,
            "phase": phase,
            "phase_confidence": round(confidence, 3),
            "phase_probabilities": phase_probs,
            "next_steps": [{"label": x["label"], "prob": x["prob"], "dir": x["dir"]} for x in next_steps],
            "dimension_scores": dim_scores,
            "fingerprint_match": fingerprint,
            "recommendation": rec,
            "entry_zone": entry,
            "stop_loss": stop,
        }

        return MMPSResult(
            phase=phase,
            phase_confidence=confidence,
            phase_probabilities=phase_probs,
            next_step_probabilities=next_steps,
            signal_scores=self._get_signal_vector(),
            dimension_scores=dim_scores,
            fingerprint_match=fingerprint,
            recommendation=rec,
            entry_zone=entry,
            stop_loss=stop,
            trigger_up=trigger_up,
            trigger_down=trigger_down,
            summary=summary,
            html_block=html_block,
            json_data=json_data,
        )


# ─────────────────────────────────────────────
# 快速使用範例
# ─────────────────────────────────────────────

def demo_3017():
    """奇鋐 3017 示範"""
    signals = MMPSSignals(
        stock_id="3017",
        stock_name="奇鋐科技",
        current_price=2505,
        price_position=0.70,        # 距高點70%位置
        concentration_score=0.3,    # 投信持續買，但外資分歧
        sentiment_score=0.4,        # 散戶已從恐慌回穩，未再追高
        volume_ratio=0.7,           # 量縮整理
        kline_score=0.4,            # 站上月線
        institutional_score=0.2,    # 投信買 外資震盪
        macro_score=0.7,            # 台股強勢 AI需求旺
        fundamental_score=0.9,      # Q1 EPS 20.17 創歷史新高
        notes="法說後利空出盡，Rubin 疑雲未完全消散，外資瑞銀仍在賣"
    )
    return MMPSAnalyzer(signals).run()


def demo_2382():
    """廣達 2382 示範"""
    signals = MMPSSignals(
        stock_id="2382",
        stock_name="廣達電腦",
        current_price=316,
        price_position=0.62,        # 中高位
        concentration_score=-0.3,   # 法說後外資賣超
        sentiment_score=-0.3,       # 散戶困惑觀望
        volume_ratio=0.8,           # 法說後量縮
        kline_score=0.1,            # 站上300但未創高
        institutional_score=-0.5,   # 三大法人法說後賣超
        macro_score=0.6,            # AI需求仍強
        fundamental_score=0.5,      # EPS創高但毛利低於預期
        notes="毛利率4.78%低於預期，下半年寄售模式能否改善是關鍵"
    )
    return MMPSAnalyzer(signals).run()


if __name__ == "__main__":
    print("=" * 60)
    print("MMPS v1.0 · 主力心態模擬預判系統 示範輸出")
    print("=" * 60)

    for demo_fn in [demo_3017, demo_2382]:
        result = demo_fn()
        print("\n" + result.summary)
        print(f"操作建議：{result.recommendation}")
        print(f"進場區間：{result.entry_zone}  停損：{result.stop_loss}")
        print(f"週期概率：", end="")
        for ph, p in sorted(result.phase_probabilities.items(), key=lambda x: -x[1]):
            print(f"{ph} {p:.0%}", end="  ")
        print("\n" + "-" * 60)

    print("\n✅ HTML 區塊已可嵌入 tw-stock-evaluator 儀表板")
    print("   使用方式：result.html_block → 插入儀表板 HTML")
    print("   JSON 資料：result.json_data → API 或前端使用")
