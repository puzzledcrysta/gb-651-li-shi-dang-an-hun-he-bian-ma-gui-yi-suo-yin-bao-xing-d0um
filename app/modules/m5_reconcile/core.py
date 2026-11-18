"""M5 索引对账。

档号逐字匹配；题名只归一可直接核过的写法差异：
- 全角/半角宽度折叠（U+FF01–U+FF5E、U+3000）
- 空白字符折叠

这里刻意不做 NFKC 兼容分解。NFKC 会把 ``①`` 变成 ``1``、``㈠`` 变成
``(一)``、``Ⅷ`` 变成 ``VIII``，等于把不同写法的原件认成同一份，属于
拿不准的差异，必须保留原题名交给人工核对。
"""
from __future__ import annotations

import re

from app.config import Settings
from app.manifest import canonical_digest, run_id

WIDTH_FIRST = 0xFF01
WIDTH_LAST = 0xFF5E
WIDTH_OFFSET = 0xFEE0
IDEOGRAPHIC_SPACE = 0x3000

DEFAULT_RULE_VERSION = Settings().rule_version

_WHITESPACE = re.compile(r"\s+", re.UNICODE)

SAMPLE = {
    "index": [
        {"archive_id": "000123", "title": "年度汇编", "source_line": 2},
        {"archive_id": "000124", "title": "附件①", "source_line": 3},
        {"archive_id": "000125", "title": "ABC-001", "source_line": 4},
        {"archive_id": "9007199254740993", "title": "会议记录", "source_line": 5},
        {"archive_id": "000404", "title": "馆藏目录", "source_line": 6},
    ],
    "transfer": [
        {"archive_id": "000123", "title": "年度　汇编", "source_line": 2},
        {"archive_id": "000124", "title": "附件1", "source_line": 3},
        {"archive_id": "000125", "title": "ＡＢＣ－００１", "source_line": 4},
        {"archive_id": "9007199254740993", "title": "会议记录", "source_line": 5},
        {"archive_id": "000777", "title": "馆藏目录", "source_line": 6},
    ],
    "quarantine": 1,
    "empty": 0,
}


def _text(value) -> str:
    return "" if value is None else str(value)


def fold_width(value: str) -> str:
    """只折叠全角/半角宽度，不做兼容字符分解。"""
    chars = []
    for ch in value:
        code = ord(ch)
        if WIDTH_FIRST <= code <= WIDTH_LAST:
            chars.append(chr(code - WIDTH_OFFSET))
        elif code == IDEOGRAPHIC_SPACE:
            chars.append(" ")
        else:
            chars.append(ch)
    return "".join(chars)


def collapse_whitespace(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def squeeze_whitespace(value: str) -> str:
    return _WHITESPACE.sub("", value)


def normalize_title(value) -> str:
    """用于展示的归一题名：折叠宽度与空白，保留其余字符原样。"""
    return collapse_whitespace(fold_width(_text(value)))


def difference_kind(index_title, transfer_title) -> str:
    left, right = _text(index_title), _text(transfer_title)
    if left == right:
        return "none"
    folded_left, folded_right = fold_width(left), fold_width(right)
    if folded_left == folded_right:
        return "width"
    if squeeze_whitespace(left) == squeeze_whitespace(right):
        return "whitespace"
    if squeeze_whitespace(folded_left) == squeeze_whitespace(folded_right):
        return "width+whitespace"
    return "content"


def _title_or_none(value):
    """空白题名按“未提供”处理，避免把两次缺题名误报成一致。"""
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def classify_title(index_title, transfer_title) -> dict:
    """把两侧题名的差异分成 SAME / STYLE / REVIEW。

    STYLE 是可直接核过的写法差异（空格、全半角），REVIEW 是不能替人
    做决定的差异（包括 ① 与 1 这类兼容字符）。
    """
    index_title = _title_or_none(index_title)
    transfer_title = _title_or_none(transfer_title)
    row = {
        "index_title_raw": index_title,
        "transfer_title_raw": transfer_title,
        "index_title_normalized": normalize_title(index_title),
        "transfer_title_normalized": normalize_title(transfer_title),
    }
    if index_title is None and transfer_title is None:
        return row | {"difference_class": "NO_TITLE", "reason_code": "TITLE_NOT_PROVIDED", "detail": "none"}
    if index_title is None or transfer_title is None:
        return row | {"difference_class": "REVIEW", "reason_code": "TITLE_ONE_SIDED", "detail": "content"}

    kind = difference_kind(index_title, transfer_title)
    if kind == "none":
        classification, code = "SAME", "TITLE_MATCH"
    elif kind in ("width", "whitespace", "width+whitespace"):
        classification, code = "STYLE", "TITLE_STYLE_ONLY"
    else:
        classification, code = "REVIEW", "TITLE_UNCERTAIN"
    return row | {"difference_class": classification, "reason_code": code, "detail": kind}


def _records(items) -> list[dict]:
    records = []
    for item in items or []:
        if isinstance(item, str):
            records.append({"archive_id": item, "title": None, "source_line": None})
            continue
        archive_id = item.get("archive_id", item.get("id", item.get("档号")))
        title = item.get("title", item.get("题名"))
        source_line = item.get("source_line", item.get("row", item.get("行号")))
        records.append(
            {
                "archive_id": str(archive_id),
                "title": title,
                "source_line": source_line,
            }
        )
    return records


def _records_from_ids(ids, titles) -> list[dict]:
    titles = titles or {}
    return [
        {"archive_id": str(item), "title": titles.get(str(item)), "source_line": None}
        for item in ids or []
    ]


def _first_by_id(records: list[dict]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for record in records:
        by_id.setdefault(record["archive_id"], record)
    return by_id


def _duplicate_conflicts(records: list[dict]) -> dict[str, list]:
    """同一档号出现多次且题名不一致：不能替人挑一条。"""
    seen: dict[str, list] = {}
    for record in records:
        seen.setdefault(record["archive_id"], []).append(record.get("title"))
    conflicts = {}
    for archive_id, titles in seen.items():
        if len(titles) < 2:
            continue
        normalized = {squeeze_whitespace(fold_width(_text(t))) for t in titles}
        if len(normalized) > 1:
            conflicts[archive_id] = titles
    return conflicts


def reconcile_records(index_records, transfer_records, quarantine=0, empty=0) -> dict:
    index_records = _records(index_records)
    transfer_records = _records(transfer_records)
    index_by_id = _first_by_id(index_records)
    transfer_by_id = _first_by_id(transfer_records)
    index_conflicts = _duplicate_conflicts(index_records)
    transfer_conflicts = _duplicate_conflicts(transfer_records)
    conflict_ids = sorted(set(index_conflicts) | set(transfer_conflicts))

    missing = sorted(set(index_by_id) - set(transfer_by_id))
    orphan = sorted(set(transfer_by_id) - set(index_by_id))
    evidence = []
    for archive_id in sorted(set(index_by_id) | set(transfer_by_id)):
        left, right = index_by_id.get(archive_id), transfer_by_id.get(archive_id)
        if left is not None and right is not None:
            row = {"archive_id": archive_id, "status": "MATCHED"}
            row |= classify_title(left.get("title"), right.get("title"))
            if archive_id in conflict_ids:
                # 同一档号在某一侧出现多个不同题名，不能替人挑一条。
                row["difference_class"] = "REVIEW"
                row["reason_code"] = "TITLE_DUPLICATE_CONFLICT"
                row["detail"] = "duplicate"
            row["index_source_line"] = left.get("source_line")
            row["transfer_source_line"] = right.get("source_line")
        elif left is not None:
            title = _title_or_none(left.get("title"))
            row = {
                "archive_id": archive_id,
                "status": "MISSING",
                "difference_class": "MISSING",
                "reason_code": "MISSING_IN_TRANSFER",
                "detail": "none",
                "index_title_raw": title,
                "transfer_title_raw": None,
                "index_title_normalized": normalize_title(title),
                "transfer_title_normalized": "",
                "index_source_line": left.get("source_line"),
                "transfer_source_line": None,
            }
        else:
            title = _title_or_none(right.get("title"))
            row = {
                "archive_id": archive_id,
                "status": "ORPHAN",
                "difference_class": "ORPHAN",
                "reason_code": "ORPHAN_IN_INDEX",
                "detail": "none",
                "index_title_raw": None,
                "transfer_title_raw": title,
                "index_title_normalized": "",
                "transfer_title_normalized": normalize_title(title),
                "index_source_line": None,
                "transfer_source_line": right.get("source_line"),
            }
        evidence.append(row)

    titled = [r for r in evidence if r["status"] == "MATCHED" and r["difference_class"] != "NO_TITLE"]
    same_count = sum(r["difference_class"] == "SAME" for r in titled)
    style_count = sum(r["difference_class"] == "STYLE" for r in titled)
    review_count = sum(r["difference_class"] == "REVIEW" for r in titled)
    title_status = "REVIEW" if review_count else "STYLE" if style_count else "OK"

    return {
        "index_count": len(index_records),
        "output_count": len(transfer_records),
        "missing": missing,
        "orphan": orphan,
        "quarantine_count": quarantine,
        "empty_count": empty,
        "balanced": len(transfer_records) + quarantine + empty >= len(transfer_by_id),
        "title_same_count": same_count,
        "title_style_count": style_count,
        "title_review_count": review_count,
        "title_status": title_status,
        "style_ids": [r["archive_id"] for r in titled if r["difference_class"] == "STYLE"],
        "review_ids": [r["archive_id"] for r in titled if r["difference_class"] == "REVIEW"],
        "conflict_ids": conflict_ids,
        "conflicts": {
            "index": index_conflicts,
            "transfer": transfer_conflicts,
        },
        "evidence": evidence,
    }


def reconcile(index_ids, normalized_ids, quarantine=0, empty=0, index_titles=None, transfer_titles=None) -> dict:
    """兼容旧调用：只给档号列表时按档号对账，题名可选。"""
    return reconcile_records(
        _records_from_ids(index_ids, index_titles),
        _records_from_ids(normalized_ids, transfer_titles),
        quarantine,
        empty,
    )


def _material(payload: dict) -> tuple[list[dict], list[dict], int, int, str]:
    if "index" in payload:
        index_records = _records(payload["index"])
    elif "index_records" in payload:
        index_records = _records(payload["index_records"])
    elif "index_ids" in payload or "index_titles" in payload:
        index_records = _records_from_ids(payload.get("index_ids", []), payload.get("index_titles"))
    else:
        index_records = list(SAMPLE["index"])

    if "transfer" in payload:
        transfer_records = _records(payload["transfer"])
    elif "transfer_records" in payload:
        transfer_records = _records(payload["transfer_records"])
    elif "normalized_ids" in payload or "transfer_titles" in payload:
        transfer_records = _records_from_ids(payload.get("normalized_ids", []), payload.get("transfer_titles"))
    else:
        transfer_records = list(SAMPLE["transfer"])

    quarantine = payload.get("quarantine", SAMPLE["quarantine"])
    empty = payload.get("empty", SAMPLE["empty"])
    rule_version = payload.get("rule_version", DEFAULT_RULE_VERSION)
    return index_records, transfer_records, quarantine, empty, rule_version


def run(payload, store=None) -> dict:
    payload = payload or {}
    store = payload.get("store", store)
    index_records, transfer_records, quarantine, empty, rule_version = _material(payload)
    out = reconcile_records(index_records, transfer_records, quarantine, empty)
    material = {
        "index": index_records,
        "transfer": transfer_records,
        "quarantine": quarantine,
        "empty": empty,
        "rule_version": rule_version,
    }
    digest = canonical_digest(material)
    rid = run_id(material)
    reason = "DIFF" if out["missing"] or out["orphan"] else "OK"
    if store is not None:
        stored = {"kind": "reconcile", "status": "READY", "run_id": rid, "digest": digest, "rule_version": rule_version, "reason": reason, **out}
        # 同一份材料重跑：digest 相同，Store 复用原批次，不新增记录。
        rid = store.record(digest, rid, stored)["run_id"]
    return {
        "status": "READY",
        "run_id": rid,
        "digest": digest,
        "rule_version": rule_version,
        "input_count": out["index_count"],
        "valid_count": out["output_count"],
        **out,
        "reason": reason,
    }
