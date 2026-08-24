import json
from pathlib import Path

from short_lease_finder.models import LeaseConfidence, Listing, ScoredListing
from short_lease_finder.output import diff_runs, load_csv, write_csv
from short_lease_finder.sources.rightmove import decode_devalue


def test_decode_devalue_roundtrip():
    # index-referenced encoding as served in window.__PAGE_MODEL
    arr = [
        {"propertyData": 1},          # 0
        {"id": 2, "tenure": 3, "ok": 6, "missing": -1, "features": 7},  # 1
        "92070276",                   # 2
        {"tenureType": 4, "yearsRemainingOnLease": 5},  # 3
        "LEASEHOLD",                  # 4
        68,                           # 5
        True,                         # 6
        [2, 4],                       # 7 (list of refs)
    ]
    model = decode_devalue({"data": json.dumps(arr), "encoding": "on"})
    pd = model["propertyData"]
    assert pd["id"] == "92070276"
    assert pd["tenure"]["yearsRemainingOnLease"] == 68
    assert pd["tenure"]["tenureType"] == "LEASEHOLD"
    assert pd["ok"] is True
    assert pd["missing"] is None
    assert pd["features"] == ["92070276", "LEASEHOLD"]


def _scored(source_id: str, price: int, score: float = 1000.0) -> ScoredListing:
    l = Listing(source="test", source_id=source_id, url=f"http://x/{source_id}",
                price=price, address=f"{source_id} Test Road", property_type="Flat",
                lease_years=70.0, lease_confidence=LeaseConfidence.EXPLICIT_YEARS)
    return ScoredListing(listing=l, score=score, v_short_est=price)


def test_csv_write_and_diff(tmp_path: Path):
    prev = tmp_path / "2026-08-23.csv"
    curr = tmp_path / "2026-08-24.csv"
    write_csv([_scored("a", 300000), _scored("b", 400000)], prev)
    write_csv([_scored("b", 385000), _scored("c", 350000)], curr)

    assert set(load_csv(prev)) == {"test:a", "test:b"}

    report = diff_runs(prev, curr)
    assert "new: 1" in report
    assert "price changes: 1" in report
    assert "withdrawn/expired: 1" in report
    assert "c Test Road" in report      # new
    assert "£400,000 -> £385,000" in report  # cut
    assert "a Test Road" in report      # gone
