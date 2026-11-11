# 飛書通知配置指南

本文只解決兩類常見訴求：

1. 把分析結果推送到飛書群
2. 避免把飛書應用模式、App Bot 主動推送和群機器人 Webhook 模式混用

## 先分清兩種模式

### 模式一：群機器人 Webhook 推送

適用場景：
- 你只想把分析報告推送到飛書群
- 不需要處理飛書消息回調
- 不需要 Stream Bot

這也是本項目最推薦、最容易落地的飛書通知方式。

需要配置的變量：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
# 按需填寫
FEISHU_WEBHOOK_SECRET=your_sign_secret
FEISHU_WEBHOOK_KEYWORD=股票日報
```

### 模式二：飛書應用 / App Bot / Stream Bot / 雲文檔

適用場景：
- 你要用飛書 App Bot 主動向指定群或用戶推送通知
- 你要做飛書應用機器人交互
- 你要啟用 Stream 模式
- 你要用飛書雲文檔能力

相關變量：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
# App Bot 主動推送時必填
FEISHU_CHAT_ID=oc_xxx
# 私聊時設置 open_id；群聊默認 chat_id
FEISHU_RECEIVE_ID_TYPE=chat_id
# 事件訂閱 / Stream Bot 時才開啟
FEISHU_STREAM_ENABLED=true
# Lark 國際版必須設置為 lark；飛書國內版保持 feishu
FEISHU_DOMAIN=feishu
```

注意：
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 不會直接開啟群 Webhook 推送
- 簡單群通知優先配置 `FEISHU_WEBHOOK_URL`
- 不用 Webhook 時，App Bot 主動推送必須同時配置 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 和 `FEISHU_CHAT_ID`
- `FEISHU_STREAM_ENABLED` 只代表事件訂閱 / Stream Bot，不參與主動通知是否配置完成的判斷
- `FEISHU_DOMAIN=lark` 會讓 App Bot 主動發送、Stream 長連接和消息回覆統一使用 `open.larksuite.com`；飛書國內版使用默認值 `feishu`
- 如果你做的是應用機器人 / Stream Bot，可直接看文末保留的原流程截圖參考
- App Bot 發送路徑複用 `requirements.txt` 中已有的 `lark-oapi>=1.0.0`，標準安裝使用 `pip install -r requirements.txt`；參考 [Feishu message create OpenAPI](https://open.feishu.cn/document/server-docs/im-v1/message/create)、[lark-oapi PyPI](https://pypi.org/project/lark-oapi/) 和 [SDK repo](https://github.com/larksuite/oapi-sdk-python)

### 文件發送模式（FEISHU_SEND_AS_FILE）

開啟後，飛書 App Bot 將報告以 `.md` 文件形式發送，而非文字/卡片消息：

```bash
FEISHU_SEND_AS_FILE=true
```

- **需要應用權限**：`im:message`（發送消息）+ `im:file`（上傳文件）
- **依賴版本**：`lark-oapi>=1.0.0` 需包含 `im.v1.file.create` API（文件上傳類）
- **Webhook 模式**：回退為發送文件內容文本（Webhook 不支持文件上傳）
- **生效範圍**：僅對 `route_type="report"` 的報告推送生效；告警、系統通知等不受影響
- **GitHub Actions 定時任務**：已通過 `.github/workflows/00-daily-analysis.yml` 映射，在 repo Settings → Secrets and variables → Actions 中添加同名變量或 secret 即可啟用
- **配置方式**：支持 `.env` 文件、GitHub Actions Secret/Variable 或 Web/桌面設置頁配置

## Webhook 推送的正確配置步驟

### 1. 在飛書群裡創建自定義機器人

路徑通常是：
- 群聊
- 群設置
- 群機器人
- 添加機器人
- 自定義機器人

完成後複製機器人提供的 Webhook URL。

示例：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 2. 查看機器人安全設置

飛書群機器人常見有三種安全限制：

1. 不加任何安全設置
2. 開啟“關鍵詞”
3. 開啟“簽名校驗”

如果你的機器人開啟了額外安全項，項目側也必須同步配置，否則請求會被飛書拒絕。

#### 開啟了關鍵詞

把飛書裡配置的同一個關鍵詞寫到：

```env
FEISHU_WEBHOOK_KEYWORD=股票日報
```

項目會自動在每條飛書消息前補上這個關鍵詞，你不需要手工改報告模板。

#### 開啟了簽名校驗

把飛書裡顯示的 secret 寫到：

```env
FEISHU_WEBHOOK_SECRET=your_sign_secret
```

項目會自動按飛書要求為每條消息補 `timestamp` 和 `sign`。

### 3. 啟動並驗證

只要配置了 `FEISHU_WEBHOOK_URL`，通知發送就會走 Webhook 通道。

如果你還同時填了：

```env
FEISHU_APP_ID=...
FEISHU_APP_SECRET=...
```

也不會影響 Webhook 推送；但它們本身不能替代 `FEISHU_WEBHOOK_URL`。

如果未配置 Webhook，也可以用 App Bot 主動推送：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_CHAT_ID=oc_xxx
FEISHU_RECEIVE_ID_TYPE=chat_id
```

此時 `FEISHU_STREAM_ENABLED` 不需要開啟；它只用於事件訂閱 / Stream Bot。

### 4. 在飛書自動化裡配置 Webhook 觸發器

如果你在飛書自動化流程裡消費本項目推送的卡片消息，請按下面配置：

1. 在創建 Webhook 觸發器時，**參數** 填寫下面 JSON（`content` 可按需保留佔位符）：

```json
{
  "msg_type": "interactive",
  "card": {
    "config": { "wide_screen_mode": true },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "..."
        }
      }
    ],
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "A股智能分析報告"
      }
    }
  }
}
```

2. 在 **操作/消息內容** 部分，不要手填純文本；點擊加號選擇 **Webhook 觸發**，並映射到：

`card.elements[0].text.content`

![img_11.png](img_11.png)

## 最常見的失敗原因

### 1. 只填了 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`

現象：
- 你覺得“飛書已經配好了”
- 實際完全收不到群通知

原因：
- 這兩個變量只是應用憑據；主動推送還需要 `FEISHU_CHAT_ID`，群 Webhook 推送則需要 `FEISHU_WEBHOOK_URL`

正確做法：
- 簡單群推送：補 `FEISHU_WEBHOOK_URL`
- App Bot 主動推送：補 `FEISHU_CHAT_ID`，並確認應用有發消息權限且機器人在目標群中

### 2. 飛書機器人開啟了關鍵詞，但本地沒配 `FEISHU_WEBHOOK_KEYWORD`

現象：
- 其他 App 能發
- 本項目發不進去，或者飛書直接返回校驗失敗

正確做法：
- 把飛書機器人安全設置中的關鍵詞原樣填到 `FEISHU_WEBHOOK_KEYWORD`

### 3. 飛書機器人開啟了簽名校驗，但本地沒配 `FEISHU_WEBHOOK_SECRET`

現象：
- Webhook URL 看起來沒問題
- 但飛書返回簽名相關錯誤

正確做法：
- 把機器人 secret 填到 `FEISHU_WEBHOOK_SECRET`

### 4. 機器人沒在目標群裡，或者沒有發言權限

檢查：
- 機器人是否真的被添加到了目標群
- 群管理員是否限制了機器人發消息

### 5. 飛書側配置了 IP 白名單

如果你在雲服務器、Docker、GitHub Actions 上跑，出口 IP 可能和本地不同。

檢查：
- 飛書機器人是否啟用了 IP 白名單
- 當前運行環境出口 IP 是否在白名單裡

## 建議的最小可用配置

### 無額外安全限制

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
```

### 開啟關鍵詞

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
FEISHU_WEBHOOK_KEYWORD=股票日報
```

### 開啟簽名校驗

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
FEISHU_WEBHOOK_SECRET=your_sign_secret
```

### 同時開啟關鍵詞和簽名

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
FEISHU_WEBHOOK_SECRET=your_sign_secret
FEISHU_WEBHOOK_KEYWORD=股票日報
```

## 排查順序建議

1. 先確認你要的是“群 Webhook 推送”還是“應用 / Stream Bot”
2. 只做簡單群推送時，先保證 `FEISHU_WEBHOOK_URL` 已配置
3. 不用 Webhook 而走 App Bot 主動推送時，確認 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_CHAT_ID` 三項齊全
4. 回到飛書機器人安全設置，確認是否啟用了關鍵詞或簽名
5. 若啟用了，就補齊 `FEISHU_WEBHOOK_KEYWORD` / `FEISHU_WEBHOOK_SECRET`
6. 最後再檢查機器人是否在群裡、是否有權限、是否命中 IP 白名單

## 附：應用 / Stream Bot 原流程截圖參考

如果你不是單純做群 Webhook 推送，而是要繼續配置飛書應用、長連接機器人或雲文檔，可以參考下面這組原截圖。

### 1. 創建應用

https://open.feishu.cn/document/develop-an-echo-bot/introduction

![img_6.png](img_6.png)

![img_8.png](img_8.png)

### 2. 獲取密鑰

![img_7.png](img_7.png)

### 3. 發佈應用

![img_5.png](img_5.png)

### 4. 在飛書中打開應用

![img_9.png](img_9.png)

### 5. 消息交互

![img_10.png](img_10.png)
