#!/usr/bin/env python3
"""按策略组把分类规则合并成可直接引用的规则集。

用法:
    python3 build_groups.py

输入:
    magicrule/groups.json          分组定义 (策略组 <- 来源分类 + 手工补充/排除)
    magicrule/surge/catalog.json   分类索引 (分类名 -> rules/<分类>.list)

输出:
    magicrule/surge/groups/<分组>.list   合并后的规则集
    magicrule/surge/groups.json          分组清单 (策略组 / 来源 / 行数)
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SURGE = ROOT / "surge"
RULES_DIR = SURGE / "rules"
GROUPS_DIR = SURGE / "groups"
CATALOG = SURGE / "catalog.json"
DEFINITIONS = ROOT / "groups.json"
MANIFEST = SURGE / "groups.json"
BASE = "https://magicrule.pages.dev"
CN_TZ = timezone(timedelta(hours=8))
UPDATED_PREFIX = "# UPDATED: "


def read_lines(path):
    """读取规则文件正文 (跳过注释)。"""
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def now_stamp():
    """当前时间 (北京时间), 用作分组文件的时间戳。"""
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S UTC+8")


def split_updated(content):
    """拆出 (时间戳, 去掉时间戳后的正文)。"""
    stamp, kept = "", []
    for line in content.splitlines():
        if line.startswith(UPDATED_PREFIX):
            stamp = line[len(UPDATED_PREFIX):].strip()
        else:
            kept.append(line)
    return stamp, "\n".join(kept) + ("\n" if kept else "")


def build():
    if not CATALOG.exists():
        print("缺少 catalog.json, 请先运行 fetch_magicrule.py", file=sys.stderr)
        return 1
    definitions = json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    known = {entry["name"].lower(): entry for entry in catalog["rules"]}
    GROUPS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    for key, spec in definitions.items():
        collected, seen, names = [], set(), []
        for source in spec.get("sources", []):
            name = source["name"] if isinstance(source, dict) else source
            pattern = source.get("filter") if isinstance(source, dict) else None
            names.append(name)
            entry = known.get(name.lower())
            if entry is None:
                print(f"  ! 分组 {key}: 缺少来源 {name}")
                continue
            for line in read_lines(RULES_DIR / Path(entry["file"]).name):
                if pattern and not re.search(pattern, line, re.IGNORECASE):
                    continue
                if line in seen:
                    continue
                seen.add(line)
                collected.append(line)

        # 手工排除: 上游条目过于宽泛, 会盖住其它分组的规则。
        excluded = set(spec.get("exclude", []))
        if excluded:
            collected = [line for line in collected if line not in excluded]

        # 手工补充: 上游没有对应分类时用, 每次重建都会写回。
        appended = 0
        for line in spec.get("extra", []):
            if line in seen:
                continue
            seen.add(line)
            collected.append(line)
            appended += 1

        header = [
            f"# NAME: {spec.get('policy', key)}",
            f"# GROUP: {key}",
            f"# SOURCE: MagicRule {BASE}",
        ]
        if names:
            header.insert(2, f"# MERGED: {', '.join(names)}")
        else:
            header.append("# MERGED: 手工维护 (无上游来源)")
        if appended:
            header.append(f"# EXTRA: {appended} 条手工补充")
        if excluded:
            header.append(f"# EXCLUDED: {len(excluded)} 条手工排除")
        header.append(f"# RULES: {len(collected)}")
        path = GROUPS_DIR / f"{key}.list"
        body = "\n".join(header + collected) + "\n"
        old_stamp, old_body = split_updated(
            path.read_text(encoding="utf-8") if path.exists() else "")
        # 规则没变就沿用旧时间戳, 只有内容真的动了才刷新 —— 避免每天产生空提交。
        if old_body != body:
            stamp = now_stamp()
        else:
            stamp = old_stamp or now_stamp()
        content = f"{UPDATED_PREFIX}{stamp}\n" + body
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
        manifest.append({
            "key": key,
            "policy": spec.get("policy", key),
            "sources": names,
            "file": f"groups/{key}.list",
            "line_count": len(collected),
            "updated": stamp,
        })
        print(f"  {key}: {len(collected)} 条 <- {', '.join(names)}")

    stamps = [entry["updated"] for entry in manifest if entry["updated"]]
    MANIFEST.write_text(json.dumps({
        "source": f"{BASE}/#/c/Surge",
        "group_count": len(manifest),
        "updated": max(stamps) if stamps else now_stamp(),
        "groups": manifest,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"分组清单: {len(manifest)} 个")
    return 0


if __name__ == "__main__":
    sys.exit(build())
