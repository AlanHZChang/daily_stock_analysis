# Discord機器人配置

## Discord機器人
Discord機器人接收消息需要使用Discord Developer Portal創建機器人應用
https://discord.com/developers/applications

Discord機器人支持兩種消息發送方式：
1. **Webhook模式**：配置簡單，權限低，適合只需要發送消息的場景
2. **Bot API模式**：權限高，支持接收命令，需要配置Bot Token和頻道ID

## 創建Discord機器人

### 1. 登錄Discord Developer Portal
訪問 https://discord.com/developers/applications 並使用你的Discord賬號登錄

### 2. 創建應用
點擊"New Application"按鈕，輸入應用名稱（例如：A股智能分析機器人），然後點擊"Create"

### 3. 配置機器人
在左側導航欄中點擊"Bot"，然後點擊"Add Bot"按鈕，確認添加

### 4. 獲取Bot Token
在Bot頁面，點擊"Reset Token"按鈕，然後複製生成的Token（這是你的`DISCORD_BOT_TOKEN`）

### 5. 配置權限
在Bot頁面的"Privileged Gateway Intents"部分，開啟以下選項：
- Presence Intent
- Server Members Intent
- Message Content Intent

### 6. 添加到服務器
1. 在左側導航欄中點擊"OAuth2" > "URL Generator"
2. 在"Scopes"中選擇：
   - `bot`
   - `applications.commands`
3. 在"Bot Permissions"中選擇：
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Use Slash Commands
4. 複製生成的URL，在瀏覽器中打開，選擇要添加機器人的服務器

### 7. 獲取頻道ID
1. 在Discord客戶端中，開啟開發者模式：設置 > 高級 > 開發者模式
2. 右鍵點擊你想要機器人發送消息的頻道，選擇"Copy ID"（這是你的`DISCORD_MAIN_CHANNEL_ID`）

## 配置環境變量

將以下配置添加到你的`.env`文件中：

```env
# Discord 機器人配置
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_MAIN_CHANNEL_ID=your-channel-id
DISCORD_WEBHOOK_URL=your-webhook-url (可選)
DISCORD_INTERACTIONS_PUBLIC_KEY=your-public-key (僅接收入站 Interaction/Webhook 回調時需要)
DISCORD_BOT_STATUS=A股智能分析 | /help
```

如果你配置了 Discord Interaction / Webhook 入站回調，務必在 Discord Developer Portal 的 `General Information -> Public Key` 複製公鑰並填入 `DISCORD_INTERACTIONS_PUBLIC_KEY`；系統會使用該公鑰校驗每個入站請求的 Ed25519 簽名，驗籤失敗會直接拒絕請求。

## Webhook模式配置（可選）

如果你只想使用Webhook模式發送消息，不需要Bot Token，可以按照以下步驟配置：

1. 右鍵點擊頻道，選擇"編輯頻道"
2. 點擊"集成" > "Webhooks" > "新建Webhook"
3. 配置Webhook名稱和頭像
4. 複製Webhook URL（這是你的`DISCORD_WEBHOOK_URL`）

## 支持的命令

Discord機器人支持以下Slash命令：

1. `/analyze <target> [full_report]` - 分析指定股票、已登記指數或股票名稱
   - `target`: 分析標的，可為股票代碼（如 `600519`）、已登記指數（如 `sh000016`、`930955.CSI`、`上证50`）或股票名稱（如 `贵州茅台`）
   - `full_report`: 可選，是否生成完整報告（包含大盤）

2. `/market_review` - 獲取大盤覆盤報告

3. `/help` - 查看幫助信息

> 邊界：`/analyze` 支持已登記指數入口與股票名稱輸入（股票名稱複用既有名稱解析器並提交 legacy code）；`/ask` 與 `/batch` 暫不支持指數輸入。

## 測試機器人

1. 確保機器人已成功添加到你的服務器
2. 在頻道中輸入`/help`，機器人會返回幫助信息
3. 輸入`/analyze 600519`測試股票分析功能（已登記指數如 `/analyze sh000016`、股票名稱如 `/analyze 貴州茅臺` 同樣可用）
4. 輸入`/market_review`測試大盤覆盤功能

## 注意事項

1. 確保你的機器人有足夠的權限在頻道中發送消息和使用Slash命令
2. 定期更新你的Bot Token，確保安全性
3. 不要將你的Bot Token分享給任何人
4. 如果機器人沒有響應，檢查：
   - Bot Token是否正確
   - 頻道ID是否正確
   - 機器人是否在線
   - 機器人是否有消息發送權限

## 故障排除

- **機器人不響應命令**：檢查Bot Token和頻道ID是否正確，確保機器人已添加到服務器
- **Slash命令不顯示**：等待一段時間（Discord需要同步命令），或重新添加機器人
- **消息發送失敗**：檢查頻道權限，確保機器人有發送消息的權限

## 相關鏈接

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord Bot Documentation](https://discordpy.readthedocs.io/en/stable/)
- [Discord Slash Commands](https://discord.com/developers/docs/interactions/application-commands)
