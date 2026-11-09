#!/usr/bin/env python3
"""从 MagicRule 抓取指定客户端的全部规则, 并生成目录索引。

用法:
    python3 fetch_magicrule.py                 # 增量抓取 Surge
    python3 fetch_magicrule.py QuantumultX    # 抓取其它客户端
    python3 fetch_magicrule.py Surge --force   # 忽略本地状态, 全量重抓

增量逻辑:
    manifest 里的 bytes_sha256 是去重归一化后的哈希, 不是原始文件校验和;
    artifact 的 URL 也不随内容严格变化 —— 两者都不能用来判断"内容是否更新"。

    所以脚本默认把每份 artifact 都拉下来, 用原始 sha256 与本地文件比对,
    只有真正变了才写盘。这样本地文件本身就是状态, 不依赖任何启发式判断,
    也不会因为上游的元数据不规范而漏更新。
    写盘前会校验内容形态 (不是 HTML、至少有一行有效规则)。
    上游删掉的规则会同步删除本地文件。

    --fast 模式改用索引里的 rule_updated_at 作为预筛, 跳过自上次以来没动过的
    规则, 省流量, 但可能漏掉"内容变了而时间戳没变"的少数情况。
    --force 强制全量重抓并忽略状态。

数据源: https://magicrule.pages.dev
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
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "*/*",
}
WORKERS = 12

# Surge 不支持的规则类型: 出现会让整份规则集加载失败。
# GEOIP 是全局规则, 放在规则集里只会触发无谓的解析, 由配置里的 GEOIP 行统一处理。
UNSUPPORTED_SURGE = {"URL-REGEX", "PROCESS-NAME", "GEOIP"}


def sanitize_surge(payload):
    """剔除 Surge 不支持的规则类型, 并按剩余内容重算头部计数。"""
    header, body = [], []
    for raw in payload.decode("utf-8", "ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if not body:
                header.append(line)
            continue
        kind = line.split(",", 1)[0].upper()
        if kind in UNSUPPORTED_SURGE:
            continue
        body.append(line)

    counts = {}
    for line in body:
        kind = line.split(",", 1)[0].upper()
        counts[kind] = counts.get(kind, 0) + 1

    # 头部形如 "# DOMAIN-SUFFIX: 249", 重算后保留原有顺序, 新出现的类型补在后面。
    fixed, order, first_at, last_at = [], [], None, None
    for index, line in enumerate(header):
        match = re.match(r"^#\s*([A-Z][A-Z0-9_-]*)\s*:\s*(\d+)\s*$", line)
        if match and match.group(1) not in ("NAME", "AUTHOR", "REPO", "UPDATED", "DESC"):
            order.append(match.group(1))
            first_at = index if first_at is None else first_at
            last_at = index
            continue
        fixed.append((index, line))
    for kind in sorted(counts):
        if kind not in order:
            order.append(kind)

    before = [line for index, line in fixed if first_at is None or index < first_at]
    after = [line for index, line in fixed if last_at is not None and index > last_at]
    lines = before + [f"# {kind}: {counts[kind]}" for kind in order if counts.get(kind)] + after
    lines.append("")
    lines.extend(body)
    return ("\n".join(lines) + "\n").encode("utf-8")


def curl(url, retries=4):
    """用 curl 拉取, 兼容部分 pages.dev 域名的 TLS 指纹问题。"""
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


def safe_name(name):
    cleaned = re.sub(r"[\\/\x00-\x1f]", "_", name).strip()
    return cleaned or "unnamed"


def sha256_of(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_client(client, out_dir, work_dir, force=False, fast=False):
    rules_dir = out_dir / "rules"
    manifests_dir = work_dir / "manifests"
    state_path = work_dir / "state.json"
    rules_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    index = get_json(f"{BASE}/data/index/{client}.json")
    rules = index["rules"]
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    print(f"{client}: {len(rules)} 条规则")

    def grab_manifest(rule):
        key = rule["manifest"].rstrip("/").split("/")[-2]
        path = manifests_dir / f"{key}.json"
        try:
            path.write_bytes(curl(rule["manifest"]))
        except Exception:
            if not path.exists():
                raise
            print(f"  manifest 拉取失败, 改用缓存: {rule['name']}")
        return key

    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(grab_manifest, rules))
    print("manifest 抓取完成")

    changed, removed, entries = [], [], []

    def grab_rule(rule):
        key = rule["manifest"].rstrip("/").split("/")[-2]
        manifest = json.loads((manifests_dir / f"{key}.json").read_text())
        artifact = next(
            (a for a in manifest.get("artifacts", [])
             if a.get("key") == "rules" and a.get("role") == "full"),
            None,
        )
        if artifact is None:
            raise RuntimeError(f"{rule['name']}: 找不到 rules artifact")

        filename = safe_name(rule["name"]) + ".list"
        path = rules_dir / filename
        updated_at = rule.get("rule_updated_at", "")
        previous = state.get(rule["name"], {})

        skip = (
            not force
            and fast
            and path.exists()
            and previous.get("rule_updated_at") == updated_at
        )
        if skip:
            digest = sha256_of(path)
        else:
            payload = curl(artifact["url"])
            head = payload[:64].lstrip().lower()
            if head.startswith(b"<!doctype") or head.startswith(b"<html"):
                raise RuntimeError(f"{rule['name']}: 抓到的不是规则文件而是 HTML")
            body = payload.decode("utf-8", "ignore")
            if not any(l.strip() and not l.strip().startswith("#")
                       for l in body.splitlines()):
                raise RuntimeError(f"{rule['name']}: 规则文件没有任何有效行")
            if client == "Surge":
                payload = sanitize_surge(payload)
            digest = hashlib.sha256(payload).hexdigest()
            old_digest = sha256_of(path) if path.exists() else None
            if old_digest != digest:
                path.write_bytes(payload)
                changed.append(f"{rule['name']}({'更新' if old_digest else '新增'})")

        body = path.read_text(encoding="utf-8", errors="ignore")
        lines = [l.strip() for l in body.splitlines() if l.strip() and not l.strip().startswith("#")]
        counts = {}
        for line in lines:
            kind = line.split(",", 1)[0].upper()
            counts[kind] = counts.get(kind, 0) + 1
        return {
            "name": rule["name"],
            "chinese_name": rule.get("chinese_name") or "",
            "description": rule.get("description") or "",
            "file": f"rules/{filename}",
            "line_count": len(lines),
            "type_counts": counts,
            "rule_updated_at": rule.get("rule_updated_at", ""),
            "providers": manifest.get("providers", []),
            "source_url": rule["manifest"],
            "sha256": digest,
        }, artifact["url"], filename, digest

    errors = []
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(grab_rule, rule): rule for rule in rules}
        for index_done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            rule = futures[future]
            try:
                entry, url, filename, digest = future.result()
            except Exception as exc:
                errors.append(f"{rule['name']}: {exc}")
                continue
            entries.append(entry)
            state[entry["name"]] = {
                "url": url,
                "file": filename,
                "rule_updated_at": entry["rule_updated_at"],
                "sha256": digest,
            }
            if index_done % 200 == 0:
                print(f"  {index_done}/{len(rules)}")

    # 上游已删除的规则, 同步清理本地文件。
    # 判定基准是上游索引本身, 而不是本次成功抓到的条目 —— 否则一次网络抖动
    # 就会把抓失败的规则当成"上游已删除"而误删本地文件。
    if not errors:
        live_files = {safe_name(r["name"]) + ".list" for r in rules}
        for path in rules_dir.glob("*.list"):
            if path.name not in live_files:
                path.unlink()
                removed.append(path.stem)
    else:
        print(f"有 {len(errors)} 条抓取失败, 跳过本地文件清理并保留原 catalog")

    entries.sort(key=lambda e: e["name"].lower())
    catalog = {
        "source": f"{BASE}/#/c/{client}",
        "client": client,
        "generated_at": index.get("generated_at", ""),
        "rule_count": len(entries),
        "total_line_count": sum(e["line_count"] for e in entries),
        "rules": entries,
    }

    # 内容没变时保留上一次的 generated_at, 避免每天产生一次无意义 diff
    catalog_path = out_dir / "catalog.json"
    if catalog_path.exists() and not changed and not removed:
        try:
            old = json.loads(catalog_path.read_text(encoding="utf-8"))
            if old.get("rules") == entries:
                catalog["generated_at"] = old.get("generated_at", catalog["generated_at"])
                print("规则内容无变化, 保留原 generated_at")
        except Exception:
            pass

    if errors:
        print("存在失败条目, 不写入 catalog, 请修复后重跑")
        for message in errors[:20]:
            print("  " + message)
        return changed, removed, errors

    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")

    with (out_dir / "catalog.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "chinese_name", "line_count", "type_counts",
                         "rule_updated_at", "file", "providers", "source_url"])
        for entry in entries:
            writer.writerow([
                entry["name"], entry["chinese_name"], entry["line_count"],
                ";".join(f"{k}:{v}" for k, v in entry["type_counts"].items()),
                entry["rule_updated_at"], entry["file"],
                ";".join(entry["providers"]), entry["source_url"],
            ])

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"完成: {catalog['rule_count']} 条, {catalog['total_line_count']} 行")
    print(f"更新 {len(changed)} 条, 删除 {len(removed)} 条")
    if changed:
        print("  " + ", ".join(sorted(changed)[:40]) + (" ..." if len(changed) > 40 else ""))
    if removed:
        print("  已删除: " + ", ".join(removed))
    return changed, removed, errors


def main():
    parser = argparse.ArgumentParser(description="抓取 MagicRule 规则集")
    parser.add_argument("client", nargs="?", default="Surge", help="客户端名称, 默认 Surge")
    parser.add_argument("--force", action="store_true", help="忽略本地状态, 全量重抓")
    parser.add_argument("--fast", action="store_true",
                        help="按 rule_updated_at 预筛, 跳过未变化的规则 (省流量, 可能漏更新)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    work_dir = root / ".work" / args.client
    work_dir.mkdir(parents=True, exist_ok=True)
    changed, removed, errors = fetch_client(
        args.client, root / args.client.lower(), work_dir,
        force=args.force, fast=args.fast)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
