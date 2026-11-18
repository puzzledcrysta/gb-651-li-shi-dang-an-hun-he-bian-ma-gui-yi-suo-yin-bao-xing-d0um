"""M6 批次导出。

导出不写批次：批次记录只由 M5 对账产生，同一份材料重跑对账复用原
run_id，重复导出也不会新增批次。

两种入参：
- ``reconcile``：M5 对账结果，导出逐条核对证据，包含两侧原题名、
  归一题名、差异分类、原因码与规则版本；
- ``rows``：旧版行清单，保持兼容。

没有显式入参时，导出读取最近一次对账批次作为依据。
"""
import csv, io

from app.manifest import canonical_digest, run_id
from app.reasons import reason as reason_text

SAMPLE={"store":None,"rows":[{"source_line":2,"archive_id":"000123","reason":"OK"},{"source_line":5,"archive_id":"BAD","reason":"BAD_COLUMNS"}]}

# 导出列固定，保证复核人员能同时看到两侧原题名、归一题名与判定依据。
EVIDENCE_FIELDS = [
    "source_line",
    "source_side",
    "archive_id",
    "status",
    "difference_class",
    "reason_code",
    "reason_text",
    "detail",
    "index_title_raw",
    "transfer_title_raw",
    "index_title_normalized",
    "transfer_title_normalized",
    "index_source_line",
    "transfer_source_line",
    "rule_version",
]

TITLE_COUNT_FIELDS = ("title_same_count", "title_style_count", "title_review_count")

# 列顺序：证据列为先，其余按名字补齐，保证旧格式仍然以 source_line,archive_id 开头。
FIELD_ORDER = EVIDENCE_FIELDS + ["reason"]


def _fieldnames(rows) -> list[str]:
    present = {key for row in rows for key in row}
    ordered = [key for key in FIELD_ORDER if key in present]
    return ordered + sorted(present - set(ordered))


def csv_text(rows):
    if not rows:
        return ""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=_fieldnames(rows), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def evidence_rows(reconcile_result: dict) -> list[dict]:
    rule_version = reconcile_result.get("rule_version", "")
    rows = []
    for item in reconcile_result.get("evidence", []):
        rows.append(
            {
                "source_line": item.get("transfer_source_line")
                if item.get("transfer_source_line") is not None
                else item.get("index_source_line"),
                # 指示 source_line 来自哪一侧：缺失行只有索引行号，孤行只有移交行号。
                "source_side": "transfer"
                if item.get("transfer_source_line") is not None
                else "index"
                if item.get("index_source_line") is not None
                else "",
                "archive_id": item.get("archive_id"),
                "status": item.get("status"),
                "difference_class": item.get("difference_class"),
                "reason_code": item.get("reason_code"),
                "reason_text": reason_text(item.get("reason_code", "")),
                "detail": item.get("detail", ""),
                "index_title_raw": item.get("index_title_raw"),
                "transfer_title_raw": item.get("transfer_title_raw"),
                "index_title_normalized": item.get("index_title_normalized"),
                "transfer_title_normalized": item.get("transfer_title_normalized"),
                "index_source_line": item.get("index_source_line"),
                "transfer_source_line": item.get("transfer_source_line"),
                "rule_version": rule_version,
            }
        )
    return rows


def _counts(reconciled: dict, rows: list[dict]) -> dict:
    counts = {
        "input_count": reconciled.get("index_count", len(rows)),
        "valid_count": reconciled.get("output_count", len(rows)),
        "quarantine_count": reconciled.get("quarantine_count", 0),
        "empty_count": reconciled.get("empty_count", 0),
        "rule_version": reconciled.get("rule_version", ""),
    }
    for key in TITLE_COUNT_FIELDS:
        counts[key] = reconciled.get(key, 0)
    return counts


def export_reconcile(reconciled: dict) -> dict:
    rows = evidence_rows(reconciled)
    digest = reconciled.get("digest") or canonical_digest(reconciled.get("evidence", []))
    rid = reconciled.get("run_id") or run_id(reconciled.get("evidence", []))
    counts = _counts(reconciled, rows)
    # 同一份材料只有一个批次：导出沿用对账批次的 run_id，不写新记录。
    return {
        "status": "READY",
        "run_id": rid,
        "digest": digest,
        "csv": csv_text(rows),
        "evidence": rows,
        **counts,
        "reason": reconciled.get("reason", "OK"),
    }


def latest_reconcile(store) -> dict | None:
    """返回最近一次对账批次（按写入顺序取最后一条）。"""
    if store is None:
        return None
    if hasattr(store, "recent"):
        items = store.recent()
    elif hasattr(store, "all"):
        items = store.all()
    else:
        return None
    for item in reversed(items):
        result = item.get("result", {})
        if result.get("kind") == "reconcile" or "evidence" in result:
            merged = {key: value for key, value in result.items() if key != "result"}
            merged["run_id"] = item["run_id"]
            merged["digest"] = item.get("digest", "")
            return merged
    return None


def no_reconcile() -> dict:
    return {
        "status": "READY",
        "run_id": None,
        "digest": None,
        "csv": "",
        "evidence": [],
        "input_count": 0,
        "valid_count": 0,
        "quarantine_count": 0,
        "empty_count": 0,
        "rule_version": "",
        "reason": "NO_RECONCILE",
    }


def run(payload):
    payload = payload or {}
    store = payload.get("store")
    if payload.get("reconcile") is not None:
        return export_reconcile(payload["reconcile"])
    if payload.get("rows") is not None:
        rows = payload["rows"]
        return {
            "status": "READY",
            "run_id": run_id(rows),
            "digest": canonical_digest(rows),
            "csv": csv_text(rows),
            "input_count": len(rows),
            "valid_count": sum(r["reason"] == "OK" for r in rows),
            "quarantine_count": sum(r["reason"] != "OK" for r in rows),
            "reason": "OK",
        }
    latest = latest_reconcile(store)
    if latest is not None:
        return export_reconcile(latest)
    if store is not None:
        return no_reconcile()
    return run({"rows": SAMPLE["rows"]})
