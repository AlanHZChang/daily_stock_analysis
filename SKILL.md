---
name: "stock_analyzer"
description: "分析股票和市場。當用戶想要分析單個或多個股票，或進行市場覆盤時調用。"
---

# 股票分析器

本技能基於 `src/services/analyzer_service.py` 的邏輯，提供分析股票和整體市場的功能。

## 輸出結構 (`AnalysisResult`)

分析函數返回一個 `AnalysisResult` 對象（或其列表），該對象具有豐富的結構。以下是其關鍵組件的簡要概述，並附有真實的輸出示例：

`dashboard` 屬性包含核心分析，分為四個主要部分：
1.  **`core_conclusion`**: 一句話總結、信號類型和倉位建議。
2.  **`data_perspective`**: 技術數據，包括趨勢狀態、價格位置、量能分析和籌碼結構。
3.  **`intelligence`**: 定性信息，如新聞、風險警報和積極催化劑。
4.  **`battle_plan`**: 可操作的策略，包括狙擊點（買/賣目標）、倉位策略和風險控制清單。

## 配置 (`Config`)

所有分析函數都可以接受一個可選的 `config` 對象。該對象包含應用程序的所有配置，例如 API 密鑰、通知設置和分析參數。

如果未提供 `config` 對象，函數將自動使用從 `.env` 文件加載的全局單例實例。

**參考:** [`Config`](src/config.py)

## 函數

### 1. 分析單隻股票

**描述:** 分析單隻股票並返回分析結果。

**何時使用:** 當用戶要求分析特定股票時。

**輸入:**
- `stock_code` (str): 要分析的股票代碼。
- `config` (Config, 可選): 配置對象。默認為 `None`。
- `full_report` (bool, 可選): 是否生成完整報告。默認為 `False`。
- `notifier` (NotificationService, 可選): 通知服務對象。默認為 `None`。

**輸出:** `Optional[AnalysisResult]`
一個包含分析結果的 `AnalysisResult` 對象，如果分析失敗則為 `None`。

**示例:**

```python
from src.services.analyzer_service import analyze_stock

# 分析單隻股票
result = analyze_stock("600989")
if result:
    print(f"股票: {result.name} ({result.code})")
    print(f"情緒得分: {result.sentiment_score}")
    print(f"操作建議: {result.operation_advice}")
```

**參考:** [`analyze_stock`](src/services/analyzer_service.py)

### 2. 分析多隻股票

**描述:** 分析一個股票列表並返回分析結果列表。

**何時使用:** 當用戶想要一次分析多隻股票時。

**輸入:**
- `stock_codes` (List[str]): 要分析的股票代碼列表。
- `config` (Config, 可選): 配置對象。默認為 `None`。
- `full_report` (bool, 可選): 是否為每隻股票生成完整報告。默認為 `False`。
- `notifier` (NotificationService, 可選): 通知服務對象。默認為 `None`。

**輸出:** `List[AnalysisResult]`
一個 `AnalysisResult` 對象列表。

**示例:**

```python
from src.services.analyzer_service import analyze_stocks

# 分析多隻股票
results = analyze_stocks(["600989", "000001"])
for result in results:
    print(f"股票: {result.name}, 操作建議: {result.operation_advice}")
```

**參考:** [`analyze_stocks`](src/services/analyzer_service.py)

### 3. 執行大盤覆盤

**描述:** 對整體市場進行復盤並返回一份報告。

**何時使用:** 當用戶要求市場概覽、摘要或覆盤時。

**輸入:**
- `config` (Config, 可選): 配置對象。默認為 `None`。
- `notifier` (NotificationService, 可選): 通知服務對象。默認為 `None`。

**輸出:** `Optional[str]`
一個包含市場覆盤報告的字符串，如果失敗則為 `None`。

**示例:**

```python
from src.services.analyzer_service import perform_market_review

# 執行大盤覆盤
report = perform_market_review()
if report:
    print(report)
```

**參考:** [`perform_market_review`](src/services/analyzer_service.py)

## 模型與外部 Bot

- 若把 **xAI Grok** 當作 DSA 分析模型：配置 `XAI_API_KEY` + `LITELLM_MODEL=xai/<官方模型ID>`（LiteLLM 直連，非託管渠道），並用 `python scripts/check_env.py --llm` 驗證。示例見 [`docs/LLM_CONFIG_GUIDE.md`](docs/LLM_CONFIG_GUIDE.md)。
- 2026-08-11 上線的 **[Grok Bot](https://x.ai/bot)** 是另一條路徑：它是帶 Skills / Routines / MCP / computer use 的 AI teammate，應通過 HTTP 調用本倉庫的 `analyze_stock` / REST API，而不是把 Bot 本身配成 LiteLLM provider。對接說明見 [`docs/grok-bot-integration.md`](docs/grok-bot-integration.md)。
