import csv
import importlib.util
import shutil

import yaml

from srp import paths
from test_pipeline_offline import CallLog, FakeClaude, FakeJev, run, write_input

spec = importlib.util.spec_from_file_location("calculator", paths.ROOT / "cost" / "calculator.py")
calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc)


def make_pilot(tmp):
    inp = tmp / "in.csv"
    write_input(inp)
    cache = tmp / "cache.db"
    run(inp, tmp / "cold", cache, tmp / "cold" / "calls.jsonl")
    run(inp, tmp / "warm", cache, tmp / "warm" / "calls.jsonl")
    base = tmp / "cost"
    base.mkdir()
    shutil.copy(paths.ROOT / "cost" / "rates.csv", base / "rates.csv")
    shutil.copy(paths.ROOT / "cost" / "assumptions.yaml", base / "assumptions.yaml")
    calc.collect(tmp / "cold", tmp / "warm", base=base)
    return base


def api_total(meas, run_label="cold"):
    return sum(m["api_cost_usd"] for m in meas if m["run"] == run_label)


def test_calculator_replay_offline_and_linear_in_rates(tmp_path):
    base = make_pilot(tmp_path)
    meas1, proj1 = calc.replay(base)
    assert api_total(meas1) > 0 and api_total(meas1, "warm") == 0  # warm run: zero new calls
    warm_enrich = [m for m in meas1 if m["run"] == "warm" and m["stage"] == "enrich"][0]
    assert warm_enrich["attempts"] == 0
    assert (base / "report.md").exists() and (base / "usage.csv").exists()

    # double every API rate -> API subtotal doubles; measured time unchanged
    rows = list(csv.DictReader(open(base / "rates.csv")))
    for r in rows:
        r["price_usd_per_unit"] = str(float(r["price_usd_per_unit"]) * 2)
    with open(base / "rates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    meas2, _ = calc.replay(base)
    assert abs(api_total(meas2) - 2 * api_total(meas1)) < 1e-12
    assert [m["stage_seconds"] for m in meas2] == [m["stage_seconds"] for m in meas1]

    # changing projected volume must not change measured pilot results
    a = yaml.safe_load((base / "assumptions.yaml").read_text())
    a["full_run"]["distinct_nonempty_texts"] = 10
    (base / "assumptions.yaml").write_text(yaml.safe_dump(a))
    meas3, proj3 = calc.replay(base)
    assert meas3 == meas2
    assert proj3 != proj1


def test_budget_warning(tmp_path):
    base = make_pilot(tmp_path)
    a = yaml.safe_load((base / "assumptions.yaml").read_text())
    a["controls"]["budget_usd"] = 0.0001
    (base / "assumptions.yaml").write_text(yaml.safe_dump(a))
    calc.replay(base)
    assert "WARNING" in (base / "report.md").read_text()
