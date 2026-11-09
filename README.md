# Surge 规则库

本仓库公开发布供 Surge 使用的规则集, 分两部分:

| 路径 | 说明 |
| --- | --- |
| `rule/MagicRule/<分类>/<分类>.list` | [MagicRule](https://magicrule.pages.dev) 全量规则库, 1185 个分类 |
| `rule/group/<分组>.list` | 按 Surge 策略组合并好的规则集, 直接可用 |
| `rule/catalog.json` / `rule/catalog.csv` | 规则清单: 分类名、行数、类型统计、更新时间、来源地址 |
| `groups.json` | 分组定义 (策略组 ← 来源分类), 修改后重跑脚本即可重组 |
| `tools/sync_magicrule.py` | 同步脚本 |

## 直接引用

    RULE-SET,https://raw.githubusercontent.com/shaoj0013/Surge/refs/heads/main/rule/group/Netflix.list,Netflix

单个分类也可以直接引:

    RULE-SET,https://raw.githubusercontent.com/shaoj0013/Surge/refs/heads/main/rule/MagicRule/Netflix/Netflix.list,Netflix

## 同步机制

`.github/workflows/sync-magicrule.yml` 每天 `04:43 UTC` (北京时间 12:43) 抓取上游,
逐个分类下载后清洗 (剔除 Surge 不支持的 `URL-REGEX` / `PROCESS-NAME`), 内容有变化才写盘,
因此不会产生无意义提交。

## 手动同步

```bash
python3 tools/sync_magicrule.py                # 全量同步
python3 tools/sync_magicrule.py --groups-only  # 只用本地文件重建分组与清单
python3 tools/sync_magicrule.py --only Netflix # 只处理指定分类
```

## 现有分组

| 分组 | 策略组 | 来源分类 |
| --- | --- | --- |
| `AdBlock` | AdBlock | AdvertisingLite |
| `AdBlock-Full` | AdBlock | Advertising |
| `AdGuard` | AdBlock | AdGuard |
| `Direct` | DIRECT | Direct |
| `AI-Suite` | AI Suite | OpenAI, Anthropic, Gemini, Copilot, GlobalAI |
| `emby` | emby | Emby |
| `TikTok` | TikTok | TikTok |
| `Netflix` / `Disney-Plus` / `Max` / `Spotify` | 同名 | Netflix, Disney, HBO 系, Spotify |
| `YouTube` | YouTube | YouTube, YouTubeMusic |
| `Asian-TV` | Asian TV | AbemaTV, Bahamut, DMM, Fox, HuluJP, iQIYIIntl, JOOX, KKBOX, KKTV, LineTV, MOOMusic, myTVSUPER, Niconico, ViuTV |
| `Global-TV` | Global TV | ABC, Amazon, BBC, DAZN, DiscoveryPlus, TVB, FOXNOW, Hulu, Pandora, PBS, SoundCloud |
| `CN-Mainland-TV` | CN Mainland TV | BiliBili, iQIYI, LeTV, NetEaseMusic, TencentVideo, Youku, WeTV |
| `Apple-TV` / `Apple-Services` / `Apple-Push` | 同名 | AppleMusic, AppleNews, AppleTV / Apple / Apple 中推送相关子集 |
| `Google-FCM` | Google FCM | Google 中 FCM 相关子集 |
| `Crypto` / `Discord` / `Microsoft` / `PayPal` / `Scholar` / `Speedtest` / `Steam` / `Telegram` / `Twitter` | 同名 | 同名分类 |
| `Facebook` / `Global` | Proxy | Facebook / Global |
| `miHoYo` | miHoYo | HoYoverse |
| `Domestic` | Domestic | China |
| `Domestic-IPs` | Domestic (需 `no-resolve`) | ChinaIPs, ChinaASN |
