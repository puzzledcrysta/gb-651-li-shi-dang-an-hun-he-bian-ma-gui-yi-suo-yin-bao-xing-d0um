import csv
import io


def test_all_module_pages(client):
    for path in ['/intake', '/encoding', '/fields', '/content', '/reconcile', '/runs']:
        response = client.get(path)
        assert response.status_code == 200
        assert "panel" in response.text

def test_all_module_apis_and_idempotent_run(client):
    for path in ['/api/intake/run', '/api/encoding/detect', '/api/fields/normalize', '/api/content/normalize', '/api/reconcile']:
        response = client.post(path, json={})
        assert response.status_code == 200
    first = client.get("/api/runs").json()
    second = client.get("/api/runs").json()
    assert len(first["runs"]) == len(second["runs"]) == 1
    assert first == second


def test_export_does_not_add_batch(client):
    reconciled = client.post("/api/reconcile", json={}).json()
    before = client.get("/api/runs").json()
    exported = client.get("/api/export/evidence.csv")
    after = client.get("/api/runs").json()
    assert exported.status_code == 200
    assert before == after
    assert len(after["runs"]) == 1
    assert reconciled["run_id"] == after["runs"][0]["run_id"]


def test_rerun_same_material_keeps_single_batch(client):
    first = client.post("/api/reconcile", json={}).json()
    second = client.post("/api/reconcile", json={}).json()
    assert first["run_id"] == second["run_id"]
    assert len(client.get("/api/runs").json()["runs"]) == 1


def test_exported_csv_is_the_reconcile_evidence(client):
    reconciled = client.post("/api/reconcile", json={}).json()
    exported = client.get("/api/export/evidence.csv")
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == len(reconciled["evidence"])
    assert {row["archive_id"] for row in rows} == {row["archive_id"] for row in reconciled["evidence"]}
    assert exported.headers["content-type"].startswith("text/csv")


def test_runs_page_shows_evidence_after_reconcile(client):
    client.post("/api/reconcile", json={})
    page = client.get("/runs")
    assert "附件①" in page.text
    assert "附件1" in page.text
