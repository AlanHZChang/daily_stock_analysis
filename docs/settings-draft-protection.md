# 設置頁草稿保護 / Unsaved settings protection

## 中文

設置頁會統一跟蹤普通配置、模型渠道和調度開關的未保存草稿，包括暫時無效的渠道名稱。切換設置分類會保留這些局部編輯。

- 刷新、關閉標籤頁或通過站內鏈接和瀏覽器前進/後退離開時，未保存草稿會觸發確認
- 取消離開保留草稿；確認放棄會清理所有草稿，並繼續前往原目標地址
- 重置會同時恢復普通配置、模型渠道和調度本地覆蓋；模型渠道仍通過獨立保存按鈕提交
- 模型保存及後續刷新進行中，重置、導入和站內確認離開需等待完成；已經發出的保存請求不會因離開頁面而撤銷
- 導入環境備份前也檢查隱藏分類中的草稿；取消導入確認保留編輯
- 從設置頁退出登錄會先明確確認丟棄未保存設置；取消保留會話和草稿，確認後退出。已發出的保存請求不因退出而撤銷；會話過期重新登錄仍保留原站內目標的 query/hash
- 服務器接受導入後清理全部舊草稿，即使隨後刷新失敗或模型渠道配置未變；導入失敗保留編輯。導入及刷新期間暫停編輯、保存、重置和確認離開，避免舊草稿覆蓋導入結果

瀏覽器決定原生刷新/關閉提示的文案與顯示條件，通常需要頁面上已有用戶交互；強制終止瀏覽器等情況無法保證彈窗。草稿只保留在當前頁面內存中，不提供自動保存或跨刷新恢復。

## English

Settings tracks unsaved generic configuration, model-channel edits, and scheduler overrides, including temporarily invalid channel names. Switching categories retains these local drafts.

- Refresh, tab close, in-app links, and browser Back/Forward warn before discarding unsaved edits
- Cancel preserves drafts; confirmed discard clears all draft owners and continues to the original destination
- Reset restores generic fields, model channels, and local scheduler overrides; model channels retain their separate Save button
- While a model save or its subsequent refresh is pending, Reset, Import, and in-app departure confirmation wait for completion; leaving cannot cancel a request already sent
- Backup import also checks drafts hidden in other categories; cancelling its confirmation preserves those edits
- Logout from Settings explicitly confirms discarding unsaved edits before ending the session. Cancel preserves the session and drafts; confirmation logs out without cancelling requests already sent. Session-expiry login redirects preserve the original internal destination's query and fragment
- Once the server accepts an import, all previous drafts are discarded even if the subsequent refresh fails or model-channel configuration is unchanged; a rejected import preserves edits. Editing, saving, resetting, and confirmed departure wait for import and refresh to finish

Native unload wording and display conditions are controlled by the browser and generally require prior user interaction. A forced browser termination cannot guarantee a prompt. Drafts live only in the current page's memory; this feature does not autosave or restore them after a refresh.
