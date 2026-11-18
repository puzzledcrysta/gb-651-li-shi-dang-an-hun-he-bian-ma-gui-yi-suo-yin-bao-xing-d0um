import pytest

from app.modules.m5_reconcile.core import (
    classify_title,
    fold_width,
    run,
    reconcile,
    reconcile_records,
)


def records(*pairs):
    return [{"archive_id": a, "title": t} for a, t in pairs]


def test_trap_1():  # TRAP-05
    assert reconcile(["001"], ["001"])["missing"] == []


def test_trap_2():
    assert reconcile(["A"], ["B"])["orphan"] == ["B"]


def test_missing_sorted():
    assert reconcile(["B", "A"], [])["missing"] == ["A", "B"]


def test_duplicates_counted_as_input():
    assert reconcile(["A", "A"], ["A"])["index_count"] == 2


def test_large_id_preserved():
    assert reconcile(["9007199254740993"], ["9007199254740993"])["missing"] == []


def test_quarantine_in_balance():
    assert reconcile(["A"], [], 1)["balanced"] is True


def test_sample_has_two_sides():
    assert run({})["reason"] == "DIFF"


def test_clean_is_ok():
    out = run({"index_ids": ["A"], "normalized_ids": ["A"], "quarantine": 0, "empty": 0})
    assert out["reason"] == "OK"
    assert out["evidence"][0]["difference_class"] == "NO_TITLE"


def test_width_fold_does_not_touch_circled_numbers():
    assert fold_width("ＡＢＣ－００１") == "ABC-001"
    assert fold_width("①") == "①"
    assert fold_width("㈠") == "㈠"


def test_whitespace_style_is_directly_verifiable():
    out = classify_title("年度汇编", "年度　汇编")
    assert out["difference_class"] == "STYLE"
    assert out["reason_code"] == "TITLE_STYLE_ONLY"
    assert out["index_title_raw"] == "年度汇编"
    assert out["transfer_title_raw"] == "年度　汇编"


def test_half_width_style_is_directly_verifiable():
    out = classify_title("ABC-001", "ＡＢＣ－００１")
    assert out["difference_class"] == "STYLE"
    assert out["index_title_normalized"] == out["transfer_title_normalized"] == "ABC-001"


def test_circled_number_is_uncertain_and_keeps_both_raw_titles():
    out = classify_title("附件①", "附件1")
    assert out["difference_class"] == "REVIEW"
    assert out["reason_code"] == "TITLE_UNCERTAIN"
    assert out["index_title_raw"] == "附件①"
    assert out["transfer_title_raw"] == "附件1"
    assert out["index_title_normalized"] != out["transfer_title_normalized"]


def test_one_sided_title_is_review():
    out = classify_title("年度汇编", None)
    assert out["difference_class"] == "REVIEW"
    assert out["reason_code"] == "TITLE_ONE_SIDED"


def test_matched_ids_pair_with_their_own_titles():
    result = reconcile_records(
        records(("000123", "年度汇编"), ("000124", "附录")),
        records(("000123", "年度　汇编"), ("000124", "附录")),
    )
    by_id = {row["archive_id"]: row for row in result["evidence"]}
    assert by_id["000123"]["difference_class"] == "STYLE"
    assert by_id["000124"]["difference_class"] == "SAME"


def test_title_counts_and_ids():
    result = reconcile_records(
        records(("1", "甲"), ("2", "乙①"), ("3", "丙")),
        records(("1", "甲"), ("2", "乙1"), ("3", "丙 ")),
    )
    assert result["title_same_count"] == 1
    assert result["title_style_count"] == 1
    assert result["title_review_count"] == 1
    assert result["style_ids"] == ["3"]
    assert result["review_ids"] == ["2"]
    assert result["title_status"] == "REVIEW"


def test_duplicate_conflicting_titles_are_not_silently_collapsed():
    result = reconcile_records(
        records(("1", "甲"), ("1", "乙")),
        records(("1", "甲")),
    )
    assert result["conflict_ids"] == ["1"]
    assert result["conflicts"]["index"]["1"] == ["甲", "乙"]


def test_duplicate_style_variants_are_not_conflicts():
    result = reconcile_records(
        records(("1", "甲")),
        records(("1", "甲"), ("1", "甲 ")),
    )
    assert result["conflict_ids"] == []


def test_numeric_and_string_ids_are_the_same_archive():
    result = reconcile_records(
        [{"archive_id": 123, "title": "甲"}],
        [{"archive_id": "123", "title": "甲"}],
    )
    assert result["missing"] == [] and result["orphan"] == []
    assert result["evidence"][0]["difference_class"] == "SAME"


def test_blank_titles_are_not_reported_as_match():
    out = classify_title("  ", " ")
    assert out["difference_class"] == "NO_TITLE"
    assert out["reason_code"] == "TITLE_NOT_PROVIDED"
    assert out["index_title_raw"] is None


def test_empty_title_on_one_side_is_review():
    out = classify_title("甲", " ")
    assert out["difference_class"] == "REVIEW"
    assert out["reason_code"] == "TITLE_ONE_SIDED"


def test_conflict_marks_the_row_review():
    result = reconcile_records(
        records(("1", "甲")),
        records(("1", "甲"), ("1", "乙")),
    )
    assert result["conflict_ids"] == ["1"]
    assert result["title_review_count"] == 1
    assert result["evidence"][0]["reason_code"] == "TITLE_DUPLICATE_CONFLICT"


def test_sample_evidence_covers_style_and_review():
    out = run({})
    assert out["style_ids"] == ["000123", "000125"]
    assert out["review_ids"] == ["000124"]
    assert out["missing"] == ["000404"]
    assert out["orphan"] == ["000777"]


class RecordingStore:
    def __init__(self):
        self.rows = {}

    def record(self, digest, rid, result):
        self.rows.setdefault(digest, (rid, result))
        stored = self.rows[digest]
        return {"run_id": stored[0], "result": stored[1]}


def test_rerun_same_material_keeps_one_batch():
    store = RecordingStore()
    first = run({"store": store})
    second = run({"store": store})
    assert first["run_id"] == second["run_id"]
    assert len(store.rows) == 1


def test_changed_title_makes_a_new_batch():
    store = RecordingStore()
    first = run(
        {
            "store": store,
            "index": [{"archive_id": "1", "title": "甲"}],
            "transfer": [{"archive_id": "1", "title": "甲"}],
            "quarantine": 0,
            "empty": 0,
        }
    )
    second = run(
        {
            "store": store,
            "index": [{"archive_id": "1", "title": "甲"}],
            "transfer": [{"archive_id": "1", "title": "乙"}],
            "quarantine": 0,
            "empty": 0,
        }
    )
    assert first["run_id"] != second["run_id"]
    assert len(store.rows) == 2


def test_sqlite_store_reuses_batch_on_rerun(tmp_path):
    from app.store import Store

    store = Store(str(tmp_path / "runs.db"))
    first = run({"store": store})
    second = run({"store": store})
    assert first["run_id"] == second["run_id"]
    assert store.count() == 1


def test_recent_keeps_insertion_order(tmp_path):
    from app.store import Store

    store = Store(str(tmp_path / "runs.db"))
    store.record("digest-b", "run-b", {"kind": "reconcile", "index_count": 1})
    store.record("digest-a", "run-a", {"kind": "reconcile", "index_count": 1})
    assert [item["run_id"] for item in store.recent()] == ["run-b", "run-a"]
