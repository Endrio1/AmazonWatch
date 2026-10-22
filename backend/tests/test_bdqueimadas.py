"""Testes unitários do parser de dados do BDQueimadas."""

from datetime import datetime, timezone

from app.ingest.bdqueimadas import parse_csv, parse_file_time


def test_parse_file_time():
    t = parse_file_time("focos_10min_20261014_1700.csv")
    assert t == datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc)

    assert parse_file_time("invalid_filename.csv") is None


def test_parse_csv():
    csv_text = """lat,lon,satelite,data
-10.500000, -55.200000,GOES-19,2026-10-14 16:50:00
-12.123400, -60.987600,NOAA-20,2026-10-14 16:55:00
invalid,data,line,here
-999.0, -55.0,GOES-19,2026-10-14 16:50:00
"""
    records = parse_csv(csv_text)
    assert len(records) == 2
    assert records[0].lat == -10.5
    assert records[0].lon == -55.2
    assert records[0].satellite == "GOES-19"
    assert records[0].detected_at == datetime(2026, 10, 14, 16, 50, tzinfo=timezone.utc)

    assert records[1].lat == -12.1234
    assert records[1].satellite == "NOAA-20"
