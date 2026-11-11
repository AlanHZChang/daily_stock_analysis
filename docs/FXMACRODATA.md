# FXMacroData 宏觀數據工具

股票分析與聊天 Agent 的工具註冊表已接入 FXMacroData。USD 數據目錄、最近 90 天的指標歷史與發佈日曆可免費使用，無需密鑰、賬戶或信用卡。

如需可選的授權數據，在運行應用的環境中配置 `FXMACRODATA_API_KEY`；使用 GitHub Actions 定時分析時，將其保存為倉庫 Secret `FXMACRODATA_API_KEY`，`00-daily-analysis.yml` 會把它映射到分析步驟環境。密鑰不會進入工具參數、模型上下文或響應。啟用 Agent 模式後，可查詢 `fxmacrodata_data_catalogue`（`currency=USD`）、`fxmacrodata_indicator_history`（`currency=USD, indicator=policy_rate`）及 `fxmacrodata_release_calendar`。

多 Agent 模式下，情報 Agent 的原生工具允許列表提供固定客戶端 v0.1.0 快照中的全部 72 個操作；風險和組合 Agent 提供與發佈、宏觀及跨市場風險相關的操作。各專業 Agent 仍遵守原有的工具訪問限制。Codex App Server 聊天后端已移除；FXMacroData 繼續通過默認聊天后端和報告 Agent 使用。

集成保留公開 API 原始數據、發佈時間、來源及推定時間標記。`records` 是用於展示的附加視圖。市場共識、官方預測和 FXMacroData 生成的預測保持區分。數據不可用時返回明確狀態，不填入模擬數據。

固定客戶端 v0.1.0 內置快照中的 23 個 REST 操作及 49 個 MCP 工具的操作表、參數、安裝及測試說明見 [English guide](FXMACRODATA_EN.md)。這兩份文檔同步介紹相同功能；完整操作名稱保持英文。

[FXMacroData](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=daily_stock_analysis_readme) · [API 文檔](https://fxmacrodata.com/documentation/reference?utm_source=github&utm_medium=referral&utm_campaign=open_source_integrations&utm_content=daily_stock_analysis_docs)
