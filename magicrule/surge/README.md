# MagicRule — Surge 规则集

从 [magicrule.pages.dev/#/c/Surge](https://magicrule.pages.dev/#/c/Surge) 抓取的完整 Surge 规则集。

| 指标 | 数值 |
| --- | --- |
| 规则条数 | 1,185 |
| 有效行数 | 855,563 |
| 规则体积 | 26.2 MB |
| 站点数据版本 | 2026-11-09 |

## 目录内容

    surge/
    ├── catalog.json    # 结构化索引 (元数据 + 行数 + 类型分布 + 上游来源 + sha256)
    ├── catalog.csv     # 同上, 表格版, UTF-8 BOM, Excel 可直接打开
    └── rules/          # 1185 个 .list 规则文件, 文件名即规则名

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
| DOMAIN-SUFFIX | 561,127 |
| DOMAIN | 246,924 |
| IP-CIDR | 31,812 |
| IP-ASN | 10,182 |
| IP-CIDR6 | 8,625 |
| DOMAIN-KEYWORD | 585 |
| PROCESS-NAME | 163 |
| USER-AGENT | 156 |
| URL-REGEX | 35 |
| GEOIP | 1 |

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
