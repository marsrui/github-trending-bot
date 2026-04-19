# GitHub Trending Discord Bot 🤖

每周日自動推送本周漲星最快的開源項目到你的 Discord，由 Claude AI 智能分類。

## 效果預覽

Discord 會收到：
- **按分類 Top 20**（AI 開發工具、設計/前端、自動化/DevOps、資料工程、安全/資安、其他）
- **本周新秀 Top 10**（7天內新建立、漲星最快的新項目）

---

## 部署步驟（5 分鐘完成）

### 1. Fork 或建立 GitHub Repo

把 `bot.py` 和 `.github/workflows/weekly_bot.yml` 放到你的 GitHub repo 裡。

目錄結構：
```
your-repo/
├── bot.py
└── .github/
    └── workflows/
        └── weekly_bot.yml
```

### 2. 建立 Discord Webhook

1. 打開你想接收訊息的 Discord 頻道
2. 頻道設定 → 整合 → Webhook → 建立 Webhook
3. 複製 Webhook URL

### 3. 設定 GitHub Secrets

進入你的 repo → Settings → Secrets and variables → Actions → New repository secret

| Secret 名稱 | 說明 |
|-------------|------|
| `ANTHROPIC_API_KEY` | 你的 Anthropic API Key（[取得](https://console.anthropic.com/)） |
| `DISCORD_WEBHOOK_URL` | 步驟 2 複製的 Webhook URL |

> `GITHUB_TOKEN` 不需要手動設定，GitHub Actions 會自動提供。

### 4. 測試執行

在 repo 的 Actions 頁面 → 找到 "GitHub Trending Discord Bot" → 點 "Run workflow" 手動觸發一次。

### 5. 自動排程

設定完成後，每周日台灣時間下午 4:00 自動執行。

---

## 修改排程時間

編輯 `weekly_bot.yml` 裡的 cron 表達式（UTC 時間）：

```yaml
- cron: "0 8 * * 0"  # 每周日 UTC 08:00 = 台灣 16:00
```

常用時間對照（台灣 UTC+8）：
- 台灣早上 9:00 = `0 1 * * 0`
- 台灣晚上 10:00 = `0 14 * * 0`

---

## 費用估算

| 項目 | 費用 |
|------|------|
| GitHub Actions | 免費（public repo 無限；private repo 每月 2000 分鐘） |
| Anthropic API | 每次約 $0.01~0.03 USD（claude-sonnet 分類 100+ 項目） |
| GitHub API | 免費（有 token 每小時 5000 次，足夠） |

每個月約 **$0.10~0.15 USD** 的 API 費用。

---

## 自訂分類

修改 `bot.py` 開頭的 `CATEGORIES` 清單即可：

```python
CATEGORIES = ["AI 開發工具", "設計 / 前端", "自動化 / DevOps", "資料工程", "安全 / 資安", "其他"]
```
