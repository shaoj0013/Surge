# MagicRule 规则聚合

从 [MagicRule](https://magicrule.pages.dev) 抓取的客户端规则集。按客户端分目录存放。

| 目录 | 客户端 | 规则数 | 有效行数 | 体积 |
| --- | --- | --- | --- | --- |
| `surge/` | Surge | 1,185 | 855,364 | 26.2 MB |

详细说明见 [`surge/README.md`](surge/README.md)。

Surge 的规则文件在抓取时会剔除它不认的三种类型 (`URL-REGEX` / `PROCESS-NAME` / `GEOIP`, 共 199 行),
否则整份规则集会被 Surge 拒绝加载; 头部注释里的类型计数同步重算。

`surge/groups/` 里另有 33 个按策略组合并好的规则集 (AdBlock / Netflix / AI Suite / Global …),
配置里直接引用这些即可, 不用逐个引用分类。合并规则写在 `groups.json`, 由
`tools/build_groups.py` 生成, 抓取脚本跑完会自动执行一次。

## 重新抓取

    cd magicrule
    python3 tools/fetch_magicrule.py Surge

脚本会增量补齐缺失文件并重建索引。`.work/` 是抓取过程中的 manifest 缓存, 不入库。

### 增量是怎么判定的

上游 manifest 里的 `bytes_sha256` 是**去重归一化后的哈希, 不是原始文件的校验和**——实测它和落地文件的原始 sha256 对不上。artifact 的 URL 里虽然带一串指纹, 也不随内容严格变化。两者都不能用来判断「内容更新了没有」。

所以脚本采用最朴素也最可靠的做法: **每份 artifact 都拉下来, 用原始 sha256 与本地文件比对, 只有真正变了才写盘**。本地文件本身就是状态, 不依赖任何启发式判断, 也不会因为上游元数据不规范而漏更新。写盘前还会校验内容形态(不是 HTML、至少有一行有效规则)。

另外两个可选项:

| 参数 | 作用 |
| --- | --- |
| `--fast` | 按索引里的 `rule_updated_at` 预筛, 跳过自上次以来没动过的规则。流量从 26MB 降到约 2MB, 耗时 1m43s → 44s, 但可能漏掉「内容变了而时间戳没变」的少数情况 |
| `--force` | 忽略全部状态, 全量重抓 |

实测: 默认模式 1m43s, `--fast` 44s, 两者在内容未变时都报告「更新 0 条」且不改动任何文件; 本地文件被破坏时, 默认模式能精确检出并还原。

## 站点接口备忘

MagicRule 是纯前端站点, 数据通过以下静态路径获取:

| 路径 | 内容 |
| --- | --- |
| `/data/index/<客户端>.json` | 该客户端的全部规则索引 |
| `/data/rules/<客户端>/<hash>/manifest.json` | 单条规则的元数据与 artifact 列表 |
| `/data/_shared/artifacts/<名称>.<ext>` | 规则文件本体 |
| `/data/meta/clients.json` | 支持的客户端列表 |
| `/data/meta/capabilities.json` | 各客户端支持的行类型与渲染选项 |

站点无批量打包端点, 未知路径会回落到 SPA 的 `index.html` (HTTP 200 但内容是 HTML), 所以批量抓取时必须校验内容类型。

## 定时更新

两条路, 各有取舍。

### 方案 A: GitHub Actions(推荐)

仓库里已经带了 `.github/workflows/magicrule.yml`:

- 每天 **04:17 UTC**(北京时间 12:17)自动跑一次
- 抓取 → 有变化就 commit + push, 没变化就不产生提交
- 也可以在 Actions 页面手动触发, 支持 `force` 和 `fast` 两个开关
- 每次运行的摘要会写进该次 workflow 的 Summary

不需要本机开机, 也不占本机资源。唯一的要求是 `permissions: contents: write`(已在文件里配好)。

注意: GitHub 会在仓库连续 60 天无活动时停用定时任务。这个仓库更新很勤, 不会触发。

### 方案 B: 本机 launchd

    cd magicrule/tools
    ./install_launchd.sh

装一个 `com.surge.magicrule` 的 LaunchAgent, 每天 05:23 本机时间跑一遍, 抓完直接推回 GitHub。

    launchctl kickstart -p gui/$(id -u)/com.surge.magicrule   # 立即试跑
    tail -f ~/Library/Logs/surge/magicrule.log                 # 看日志
    ./install_launchd.sh --uninstall                           # 卸载

本机方案有个坑: `git push` 依赖 `gh` 的钥匙串凭据, 而后台任务在钥匙串锁定时读不到密码, 会静默失败。想避开就用方案 A——云端用 `GITHUB_TOKEN`, 没有这个问题。

### 两条别同时开

两个方案都往同一个 `main` 分支推, 同时开会互相覆盖。选一个就行。
