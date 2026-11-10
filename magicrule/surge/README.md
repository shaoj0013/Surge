# MagicRule — Surge 规则集

从 [magicrule.pages.dev/#/c/Surge](https://magicrule.pages.dev/#/c/Surge) 抓取的完整 Surge 规则集。

| 指标 | 数值 |
| --- | --- |
| 规则条数 | 1,185 |
| 有效行数 | 855,364 |
| 规则体积 | 26.2 MB |
| 站点数据版本 | 2026-11-09 |

## 目录内容

    surge/
    ├── catalog.json    # 结构化索引 (元数据 + 行数 + 类型分布 + 上游来源 + sha256)
    ├── catalog.csv     # 同上, 表格版, UTF-8 BOM, Excel 可直接打开
    ├── rules/          # 1185 个 .list 规则文件, 文件名即规则名
    ├── groups/         # 37 个按策略组合并好的规则集, 直接可用
    └── groups.json     # 分组清单 (策略组 / 来源分类 / 行数)

## 规则格式

标准 Surge 规则集格式, 每个文件自带头部注释:

    # NAME: 115
    # AUTHOR: MagicRule
    # REPO: https://magicrule.pages.dev
    # UPDATED: 2026-11-07 03:20:35
    # DOMAIN: 1
    # DOMAIN-SUFFIX: 14

    DOMAIN,fhnfile.oss-cn-shenzhen.aliyuncs.com
    DOMAIN-SUFFIX,115.com
    DOMAIN-SUFFIX,115cdn.com

支持的行类型及数量:

| 类型 | 行数 |
| --- | --- |
| DOMAIN-SUFFIX | 557,267 |
| DOMAIN | 246,764 |
| IP-CIDR | 31,785 |
| IP-ASN | 10,182 |
| IP-CIDR6 | 8,625 |
| DOMAIN-KEYWORD | 585 |
| USER-AGENT | 156 |

上游混着三种 Surge 不认的规则类型, 抓取时已剔除, 否则整份规则集加载失败:
`URL-REGEX` 35 条、`PROCESS-NAME` 163 条、`GEOIP` 1 条 (共 199 行)。
`GEOIP` 是全局规则, 放在规则集里只会触发无谓的解析, 由配置里的 `GEOIP,CN,...` 统一处理。
头部注释里的类型计数会按剔除后的内容重算。

## 合并分组

`groups/` 里的 37 个文件是按 Surge 策略组合并好的规则集, 建议直接引用它们, 而不是逐个引用分类:

    [Rule]
    RULE-SET,https://your-host/magicrule/surge/groups/AdBlock.list,AdBlock
    RULE-SET,https://your-host/magicrule/surge/groups/AI-Suite.list,AI Suite

合并规则写在 `magicrule/groups.json` 里, 支持四个字段:

| 字段 | 说明 |
| --- | --- |
| `sources` | 来源分类; `{"name": "X", "filter": "正则"}` 表示只取 X 中匹配该正则的规则 |
| `extra` | 手工补充的规则 (上游没有对应分类时用) |
| `exclude` | 手工排除的规则 (上游条目过于宽泛、会盖住其它分组时用) |
| `refresh` | `true` 时每次抓取都刷新该分组的 `# UPDATED:` (表示最近一次检查时间); 默认只在规则内容变化时刷新 |

例如 `AI-Suite` 排除了 `DOMAIN-SUFFIX,microsoft.com` —— 上游 `GlobalAI` 分类里带着这条,
会导致整个 `microsoft.com` 都走 AI Suite 分组而不是 Microsoft 分组。

合并由 `magicrule/tools/build_groups.py` 完成, 抓取脚本跑完会自动执行一次。

每个分组文件的第一行是 `# UPDATED:`, 记录该分组**最后一次内容变化**的时间 (北京时间)。
规则没变时这个时间戳保持不变, 不会每天刷新 —— 靠它可以判断一份规则集是不是真的更新过。

## 在 Surge 中使用

把 `rules/` 目录部署到可访问的 URL 下, 然后在配置中引用:

    [Rule]
    RULE-SET,https://your-host/magicrule/surge/rules/Advertising.list
    RULE-SET,https://your-host/magicrule/surge/rules/China.list
    RULE-SET,https://your-host/magicrule/surge/rules/Global.list

或者把整个目录克隆到本地, 用 `file://` 路径引用。

## 上游来源

1,172 / 1,185 条规则标注了上游仓库, 主要来自:

- `github.com` / `raw.githubusercontent.com` — 各类公开规则仓库
- `ruleset.skk.moe`
- `adguardteam.github.io`

每条规则的上游地址见 `catalog.json` 的 `providers` 字段。

## 更新

    cd magicrule
    python3 tools/fetch_magicrule.py          # 默认抓 Surge
    python3 tools/fetch_magicrule.py Surge   # 也可显式指定

脚本会复用已下载的文件, 只补齐缺失部分, 并重新生成 `catalog.json` 与 `catalog.csv`。

## 说明

- 站点同时提供 `DOMAIN-SET` 变体 (给非 Surge 客户端用), 本目录只收录 **完整规则** 变体
- 规则内容全部来自上游各公开仓库, 本目录仅做聚合与索引, 不修改任何规则行
- 抓取时间与站点数据版本见 `catalog.json` 的 `generated_at`
