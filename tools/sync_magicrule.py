#!/usr/bin/env python3
"""把 MagicRule 的 Surge 规则集同步到本仓库, 并生成规则清单与策略组合并集。

产出:
    rule/MagicRule/<分类>/<分类>.list   上游规则集 (清洗后)
    rule/group/<分组>.list               按 Surge 策略组合并的规则集
    rule/catalog.json                    规则清单 (全部分类的元数据)
    rule/catalog.csv                     规则清单 (表格)

用法:
    python3 tools/sync_magicrule.py                # 全量同步
    python3 tools/sync_magicrule.py --groups-only  # 只用本地已有文件重建合并集与清单
    python3 tools/sync_magicrule.py --only Netflix,Apple
"""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://magicrule.pages.dev"
ROOT = Path(__file__).resolve().parent.parent
MIRROR = ROOT / "rule" / "MagicRule"
GROUP_DIR = ROOT / "rule" / "group"
CATALOG_JSON = ROOT / "rule" / "catalog.json"
CATALOG_CSV = ROOT / "rule" / "catalog.csv"
GROUPS_FILE = ROOT / "groups.json"

# URL-REGEX / PROCESS-NAME 是 Surge 不支持的类型, 出现会让整份规则集加载失败;
# GEOIP 是全局规则, 放在规则集里会触发无谓的解析, 由配置里的 GEOIP 行统一处理。
UNSUPPORTED = {"URL-REGEX", "PROCESS-NAME", "GEOIP"}
WORKERS = 12
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "*/*",
}


def curl(url, retries=4):
    """用 curl 拉取, 绕开部分 pages.dev 域名的 TLS 指纹问题。"""
    last = None
    for attempt in range(retries):
        try:
            result = subprocess.run(
                ["curl", "-sSL", "--fail", "--max-time", "90", "--retry", "2",
                 "-A", UA["User-Agent"], url],
                capture_output=True,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
            last = result.stderr.decode("utf-8", "ignore")[:200] or f"curl rc={result.returncode}"
        except Exception as exc:
            last = str(exc)
        time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def get_json(url):
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def read_lines(path):
    """读取已落盘的规则文件正文 (跳过注释)。"""
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def sanitize(payload, meta):
    """剔除 Surge 不支持的规则类型, 并统一注释头。"""
    dropped = {}
    lines = []
    for raw in payload.decode("utf-8", "ignore").splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        rule_type = text.split(",", 1)[0].upper()
        if rule_type in UNSUPPORTED:
            dropped[rule_type] = dropped.get(rule_type, 0) + 1
            continue
        lines.append(text)

    header = [
        f"# NAME: {meta['name']}",
        f"# SOURCE: {meta['source_url']}",
        f"# UPDATED: {meta['updated']}",
        f"# RULES: {len(lines)}",
    ]
    if dropped:
        header.append("# STRIPPED: " + ", ".join(f"{key}x{value}" for key, value in sorted(dropped.items())))
    return "\n".join(header + lines) + "\n", dropped


def write_if_changed(path, content):
    """内容有变化才落盘, 避免每天产生无意义提交。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def fetch_rules(only=None):
    """下载上游规则集 (按需清洗后落盘), 并返回带完整元数据的清单。"""
    index = get_json(f"{BASE}/data/index/Surge.json")
    rules = index["rules"]
    targets = rules
    if only:
        wanted = {name.lower() for name in only}
        targets = [rule for rule in rules if rule["name"].lower() in wanted]
    print(f"上游共 {len(rules)} 个分类, 本次下载 {len(targets)} 个")

    def grab(rule):
        manifest = get_json(rule["manifest"])
        artifact = next(
            (item for item in manifest.get("artifacts", [])
             if item.get("key") == "rules" and item.get("role") == "full"),
            None,
        )
        if artifact is None:
            raise RuntimeError(f"{rule['name']}: 找不到 rules artifact")
        payload = curl(artifact["url"])
        head = payload[:64].lstrip().lower()
        if head.startswith(b"<!doctype") or head.startswith(b"<html"):
            raise RuntimeError(f"{rule['name']}: 抓到的是 HTML 而不是规则文件")

        meta = {
            "name": rule["name"],
            "source_url": rule["manifest"],
            "updated": rule.get("rule_updated_at", ""),
        }
        content, dropped = sanitize(payload, meta)
        target = MIRROR / rule["name"] / f"{rule['name']}.list"
        changed = write_if_changed(target, content)
        return rule, len(read_lines(target)), dropped, changed

    errors = []
    changed = 0
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(grab, rule): rule for rule in targets}
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            rule = futures[future]
            try:
                _, _, _, was_changed = future.result()
                changed += 1 if was_changed else 0
            except Exception as exc:
                errors.append(f"{rule['name']}: {exc}")
            if done % 200 == 0:
                print(f"  {done}/{len(targets)}")

    if errors:
        print(f"有 {len(errors)} 个分类抓取失败:")
        for message in errors[:20]:
            print("  " + message)
    print(f"内容有变化: {changed} 个")
    return build_entries(rules), errors


def build_entries(rules):
    """清单 = 上游元数据 + 本地文件的实际行数。"""
    entries = []
    for rule in rules:
        name = rule["name"]
        path = MIRROR / name / f"{name}.list"
        stripped = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:12]:
                if line.startswith("# STRIPPED:"):
                    for item in line.split(":", 1)[1].split(","):
                        key, _, value = item.strip().partition("x")
                        if value.isdigit():
                            stripped[key] = int(value)
        entries.append({
            "name": name,
            "chinese_name": rule.get("chinese_name") or "",
            "description": rule.get("description") or "",
            "file": f"rule/MagicRule/{name}/{name}.list",
            "line_count": len(read_lines(path)),
            "type_counts": rule.get("type_counts", {}),
            "rule_updated_at": rule.get("rule_updated_at", ""),
            "source_url": rule["manifest"],
            "stripped": stripped,
        })
    return entries


def build_groups(entries):
    """按策略组合并规则集。"""
    groups = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    known = {entry["name"].lower(): entry for entry in entries}
    built = []
    for key, spec in groups.items():
        collected, seen = [], set()
        names = []
        for source in spec["sources"]:
            name = source["name"] if isinstance(source, dict) else source
            pattern = source.get("filter") if isinstance(source, dict) else None
            names.append(name)
            entry = known.get(name.lower())
            if entry is None:
                print(f"  ! 分组 {key}: 缺少来源 {name}")
                continue
            path = ROOT / entry["file"]
            for line in read_lines(path):
                if pattern and not re.search(pattern, line, re.IGNORECASE):
                    continue
                if line in seen:
                    continue
                seen.add(line)
                collected.append(line)

        # 手工排除的规则: 上游条目过于宽泛, 会盖住其它分组的规则。
        excluded = set(spec.get("exclude", []))
        if excluded:
            collected = [line for line in collected if line not in excluded]
            seen -= excluded

        # 手工补充的规则 (上游没有对应分类时用), 每次重建都会重新写入。
        extras = spec.get("extra", [])
        appended = 0
        for line in extras:
            if line in seen:
                continue
            seen.add(line)
            collected.append(line)
            appended += 1

        header = [
            f"# NAME: {spec.get('policy', key)}",
            f"# GROUP: {key}",
            f"# MERGED: {', '.join(names)}",
            f"# SOURCE: MagicRule {BASE}",
            f"# RULES: {len(collected)}",
        ]
        if appended:
            header.insert(4, f"# EXTRA: {appended} 条手工补充")
        if excluded:
            header.insert(4, f"# EXCLUDED: {len(excluded)} 条手工排除")
        content = "\n".join(header + collected) + "\n"
        path = GROUP_DIR / f"{key}.list"
        write_if_changed(path, content)
        built.append({
            "key": key,
            "policy": spec.get("policy", key),
            "sources": names,
            "file": f"rule/group/{key}.list",
            "line_count": len(collected),
        })
        print(f"  {key}: {len(collected)} 条 <- {', '.join(names)}")
    return built


def write_catalog(entries, groups):
    """写出规则清单。"""
    entries = sorted(entries, key=lambda item: item["name"].lower())
    catalog = {
        "source": f"{BASE}/#/c/Surge",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule_count": len(entries),
        "total_line_count": sum(item["line_count"] for item in entries),
        "rules": entries,
        "groups": groups,
    }
    CATALOG_JSON.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")

    with CATALOG_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "chinese_name", "line_count", "type_counts",
                         "rule_updated_at", "file", "source_url"])
        for entry in entries:
            writer.writerow([
                entry["name"], entry["chinese_name"], entry["line_count"],
                ";".join(f"{key}:{value}" for key, value in (entry.get("type_counts") or {}).items()),
                entry["rule_updated_at"], entry["file"], entry["source_url"],
            ])
    print(f"清单: {catalog['rule_count']} 个分类, {catalog['total_line_count']} 行")


def main():
    parser = argparse.ArgumentParser(description="同步 MagicRule 规则集")
    parser.add_argument("--groups-only", action="store_true", help="不联网, 只重建合并集与清单")
    parser.add_argument("--only", help="只处理指定分类, 逗号分隔")
    args = parser.parse_args()

    only = [name for name in (args.only or "").split(",") if name.strip()] or None
    if args.groups_only:
        index = get_json(f"{BASE}/data/index/Surge.json")
        entries = build_entries(index["rules"])
    else:
        entries, errors = fetch_rules(only)
        if errors:
            print("存在失败分类, 清单可能不完整")

    print("生成策略组合并集:")
    groups = build_groups(entries)
    write_catalog(entries, groups)
    return 0


if __name__ == "__main__":
    sys.exit(main())
