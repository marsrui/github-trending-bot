"""
GitHub Trending Discord Bot
每周日自動抓取 GitHub 漲星快的開源項目，用 Claude 分類後發送到 Discord
"""

import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic

# ── 設定區 ────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN        = os.environ.get("GITHUB_TOKEN", "")  # 選填，有的話不容易被限速

client = Anthropic(api_key=ANTHROPIC_API_KEY)

CATEGORIES = ["AI 開發工具", "設計 / 前端", "自動化 / DevOps", "資料工程", "安全 / 資安", "其他"]

# ── GitHub 抓資料 ─────────────────────────────────────────

def get_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def fetch_trending_repos(days=7, min_stars=50, limit=120):
    """抓過去 N 天漲星快的 repo"""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"stars:>{min_stars} created:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 100),
    }
    r = requests.get(url, headers=get_headers(), params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("items", [])

    # 補抓第二頁
    if limit > 100:
        params["page"] = 2
        params["per_page"] = limit - 100
        r2 = requests.get(url, headers=get_headers(), params=params, timeout=30)
        if r2.ok:
            items += r2.json().get("items", [])

    return items

def fetch_popular_repos(days=7, limit=80):
    """抓既有老項目這一周漲很快的（用 pushed 日期篩選後按 stars 排序）"""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"stars:>1000 pushed:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": 100,
    }
    r = requests.get(url, headers=get_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("items", [])

def extract_repo_info(repo):
    return {
        "name": repo["full_name"],
        "description": (repo.get("description") or "")[:120],
        "stars": repo["stargazers_count"],
        "language": repo.get("language") or "N/A",
        "url": repo["html_url"],
        "created_at": repo.get("created_at", "")[:10],
        "topics": repo.get("topics", [])[:5],
    }

# ── Claude 分類 ───────────────────────────────────────────

def classify_repos(repos: list[dict]) -> list[dict]:
    """讓 Claude 幫每個 repo 加上分類標籤"""
    simplified = [
        {"name": r["name"], "description": r["description"], "topics": r["topics"]}
        for r in repos
    ]
    prompt = f"""你是一個開源項目分類專家。
請把以下 GitHub 項目各自分到最符合的類別之一：
{json.dumps(CATEGORIES, ensure_ascii=False)}

項目列表（JSON）：
{json.dumps(simplified, ensure_ascii=False)}

請只回傳 JSON 陣列，每個元素格式：{{"name": "owner/repo", "category": "類別名稱"}}
不要加任何說明文字。"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    # 去除可能的 markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    classifications = json.loads(raw.strip())

    cat_map = {item["name"]: item["category"] for item in classifications}
    for r in repos:
        r["category"] = cat_map.get(r["name"], "其他")
    return repos

# ── 排名邏輯 ──────────────────────────────────────────────

def build_top20_by_category(all_repos: list[dict]) -> dict:
    """按總星數排名，每個分類最多顯示到 Top 20"""
    sorted_repos = sorted(all_repos, key=lambda x: x["stars"], reverse=True)
    result = {cat: [] for cat in CATEGORIES}
    seen = set()
    for r in sorted_repos:
        cat = r.get("category", "其他")
        if cat not in result:
            cat = "其他"
        if r["name"] not in seen and len(result[cat]) < 20:
            result[cat].append(r)
            seen.add(r["name"])
    return result

def build_new_rising_top10(new_repos: list[dict]) -> list[dict]:
    """本周新項目，按星數取 Top 10"""
    return sorted(new_repos, key=lambda x: x["stars"], reverse=True)[:10]

# ── Discord 訊息格式化 ────────────────────────────────────

def stars_bar(stars: int) -> str:
    """簡單的星星數視覺化"""
    if stars >= 5000:  return "🌟🌟🌟🌟🌟"
    if stars >= 2000:  return "🌟🌟🌟🌟"
    if stars >= 1000:  return "🌟🌟🌟"
    if stars >= 500:   return "🌟🌟"
    return "🌟"

CATEGORY_EMOJI = {
    "AI 開發工具":     "🤖",
    "設計 / 前端":     "🎨",
    "自動化 / DevOps": "⚙️",
    "資料工程":        "📊",
    "安全 / 資安":     "🔐",
    "其他":            "📦",
}

def format_repo_line(r: dict, rank: int) -> str:
    lang = f"`{r['language']}`" if r["language"] != "N/A" else ""
    desc = r["description"][:80] + "…" if len(r["description"]) > 80 else r["description"]
    return (
        f"**{rank}.** [{r['name']}]({r['url']}) {stars_bar(r['stars'])}\n"
        f"   ⭐ {r['stars']:,}  {lang}  {desc}\n"
    )

def build_discord_embeds(top20_by_cat: dict, new_rising: list[dict]) -> list[dict]:
    today = datetime.utcnow().strftime("%Y/%m/%d")
    embeds = []

    # ── Header embed
    embeds.append({
        "title": f"📈 GitHub 開源項目周報　{today}",
        "description": (
            "本周漲星最快 + 新冒頭項目整理，每週日自動推送。\n"
            "---\n"
            "**📊 按分類 Top 20**　|　**🚀 本周新秀 Top 10**"
        ),
        "color": 0x7289DA,
    })

    # ── 各分類 Top embed（有資料才顯示）
    for cat in CATEGORIES:
        repos = top20_by_cat.get(cat, [])
        if not repos:
            continue
        emoji = CATEGORY_EMOJI.get(cat, "📦")
        lines = [format_repo_line(r, i + 1) for i, r in enumerate(repos)]
        embeds.append({
            "title": f"{emoji} {cat}　Top {len(repos)}",
            "description": "\n".join(lines)[:4000],
            "color": 0x57F287,
        })

    # ── 本周新秀 Top 10
    if new_rising:
        lines = []
        for i, r in enumerate(new_rising):
            created = r.get("created_at", "")
            lines.append(
                f"**{i+1}.** [{r['name']}]({r['url']}) {stars_bar(r['stars'])}\n"
                f"   ⭐ {r['stars']:,}  📅 {created}  `{r['language']}`  {r['description'][:70]}\n"
            )
        embeds.append({
            "title": "🚀 本周新秀 Top 10（7天內爆炸性漲星）",
            "description": "\n".join(lines)[:4000],
            "color": 0xFEE75C,
        })

    return embeds

def send_to_discord(embeds: list[dict]):
    """Discord 一次最多 10 個 embed，超過要分批"""
    batch_size = 10
    for i in range(0, len(embeds), batch_size):
        batch = embeds[i:i + batch_size]
        payload = {"embeds": batch}
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        r.raise_for_status()
        print(f"✅ 發送 embed {i+1}~{i+len(batch)} 成功")

# ── 主流程 ────────────────────────────────────────────────

def main():
    print("🔍 抓取 GitHub 資料中...")
    new_raw   = fetch_trending_repos(days=7, min_stars=30, limit=120)
    all_raw   = fetch_popular_repos(days=7, limit=80)

    # 合併去重
    seen_names = set()
    combined = []
    for r in new_raw + all_raw:
        info = extract_repo_info(r)
        if info["name"] not in seen_names:
            combined.append(info)
            seen_names.add(info["name"])
    print(f"📦 共 {len(combined)} 個項目，開始 Claude 分類...")

    classified = classify_repos(combined)

    # 新項目 = 7天內建立的
    cutoff = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    new_repos_only = [r for r in classified if r.get("created_at", "") >= cutoff]

    top20_by_cat = build_top20_by_category(classified)
    new_rising   = build_new_rising_top10(new_repos_only)

    print("📨 組裝並發送 Discord 訊息...")
    embeds = build_discord_embeds(top20_by_cat, new_rising)
    send_to_discord(embeds)
    print("🎉 完成！")

if __name__ == "__main__":
    main()
