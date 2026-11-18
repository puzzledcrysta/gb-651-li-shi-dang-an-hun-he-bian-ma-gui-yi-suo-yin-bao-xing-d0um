import csv
import io

from app.modules.m5_reconcile import core as m5
from app.modules.m6_runs.core import csv_text, evidence_rows, run
from app.modules.m6_runs.core import SAMPLE


class FakeStore:
    def __init__(self):
        self.values = {}

    def record(self, digest, rid, result):
        self.values.setdefault(digest, (rid, result))
        return {"run_id": self.values[digest][0], "result": self.values[digest][1]}


class ListStore:
    """按写入顺序保留批次；重复摘要不新增。"""

    def __init__(self):
        self.items = []
        self.index = {}

    def record(self, digest, rid, result):
        if digest not in self.index:
            self.index[digest] = len(self.items)
            self.items.append({"run_id": rid, "digest": digest, "result": result})
        stored = self.items[self.index[digest]]
        return {"run_id": stored["run_id"], "result": stored["result"]}

    def all(self):
        return sorted(self.items, key=lambda item: item["run_id"])

    def recent(self):
        return list(self.items)


def parsed(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_csv_header(): assert csv_text(SAMPLE["rows"]).startswith("source_line,archive_id,reason")
def test_csv_preserves_zero(): assert "000123" in csv_text(SAMPLE["rows"])
def test_run_id_stable(): assert run({})["run_id"] == run({})["run_id"]
def test_digest_stable(): assert run({})["digest"] == run({})["digest"]
def test_trap_1():  # TRAP-07
    store=FakeStore(); assert run({"store":store})["run_id"]==run({"store":store})["run_id"]
def test_trap_2():
    assert run({"rows":SAMPLE["rows"]})["input_count"]==2
def test_counts_quarantine(): assert run({})["quarantine_count"]==1
def test_counts_valid(): assert run({})["valid_count"]==1


def test_evidence_export_has_both_raw_titles_and_verdict():
    reconciled = m5.run({})
    out = run({"reconcile": reconciled})
    rows = parsed(out["csv"])
    by_id = {row["archive_id"]: row for row in rows}
    assert by_id["000123"]["difference_class"] == "STYLE"
    assert by_id["000124"]["difference_class"] == "REVIEW"
    assert by_id["000123"]["index_title_raw"] == "年度汇编"
    assert by_id["000123"]["transfer_title_raw"] == "年度　汇编"
    assert by_id["000124"]["index_title_raw"] == "附件①"
    assert by_id["000124"]["transfer_title_raw"] == "附件1"
    assert by_id["000124"]["reason_code"] == "TITLE_UNCERTAIN"
    assert by_id["000404"]["status"] == "MISSING"
    assert all(row["rule_version"] for row in rows)


def test_evidence_export_keeps_source_lines():
    reconciled = m5.run({})
    rows = evidence_rows(reconciled)
    by_id = {row["archive_id"]: row for row in rows}
    assert by_id["000123"]["source_line"] == 2
    assert by_id["000123"]["index_source_line"] == 2
    assert by_id["000404"]["source_line"] == 6


def test_export_reuses_reconcile_run_id_and_adds_no_batch():
    store = ListStore()
    first = m5.run({"store": store})
    exported = run({"store": store})
    again = run({"store": store})
    assert exported["run_id"] == first["run_id"] == again["run_id"]
    assert len(store.items) == 1


def test_rerun_reconcile_same_material_does_not_add_batch():
    store = ListStore()
    first = m5.run({"store": store})
    second = m5.run({"store": store})
    run({"store": store})
    assert first["run_id"] == second["run_id"]
    assert len(store.items) == 1


def test_export_without_reconcile_is_empty_not_error():
    out = run({"store": ListStore()})
    assert out["reason"] == "NO_RECONCILE"
    assert out["csv"] == ""
    assert out["evidence"] == []
