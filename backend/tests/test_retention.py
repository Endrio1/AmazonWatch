import os
from datetime import datetime, timedelta, timezone

from app.ingest.retention import remove_expired_files


def test_retention_boundary_and_file_scope(tmp_path):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)
    for name, age in [("old.nc", 49), ("recent.nc", 47), ("boundary.nc", 48),
                      ("download_interrupted.part", 49), ("unrelated.txt", 49)]:
        path = tmp_path / name
        path.write_text("data")
        timestamp = (now - timedelta(hours=age)).timestamp()
        os.utime(path, (timestamp, timestamp))
    outside = tmp_path / "unrelated.txt"
    (tmp_path / "linked.nc").symlink_to(outside)
    assert remove_expired_files(tmp_path, ("*.nc", "download_*.part"), cutoff) == 2
    assert {p.name for p in tmp_path.iterdir()} == {
        "recent.nc", "boundary.nc", "unrelated.txt", "linked.nc"
    }


def test_orphan_images_are_removed_and_missing_directory_is_safe(tmp_path):
    path = tmp_path / "satellite_20260101_1200.jpg"
    path.write_bytes(b"image")
    os.utime(path, (0, 0))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    assert remove_expired_files(tmp_path, ("satellite_*.jpg",), cutoff) == 1
    assert remove_expired_files(tmp_path / "missing", ("*.nc",), cutoff) == 0


def test_deletion_failure_does_not_stop_cleanup(tmp_path, monkeypatch):
    from pathlib import Path
    for name in ("locked.nc", "expired.nc"):
        path = tmp_path / name
        path.touch()
        os.utime(path, (0, 0))
    unlink = Path.unlink

    def fail_one(path, **kwargs):
        if path.name == "locked.nc":
            raise PermissionError("locked")
        return unlink(path, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one)
    assert remove_expired_files(tmp_path, ("*.nc",), datetime.now(timezone.utc)) == 1
    assert (tmp_path / "locked.nc").exists()


def test_legacy_tmp_netcdf_cleanup_is_scoped(tmp_path):
    now = datetime.now(timezone.utc)
    for name, hours in [("tmpold.nc", 49), ("tmprecent.nc", 47),
                        ("other.nc", 49), ("tmpother.txt", 49)]:
        path = tmp_path / name
        path.touch()
        stamp = (now - timedelta(hours=hours)).timestamp()
        os.utime(path, (stamp, stamp))
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "tmpold.nc").touch()
    os.utime(nested / "tmpold.nc", (0, 0))
    (tmp_path / "tmplink.nc").symlink_to(tmp_path / "other.nc")
    assert remove_expired_files(tmp_path, ("tmp*.nc",), now - timedelta(hours=48)) == 1
    assert not (tmp_path / "tmpold.nc").exists()
    assert all((tmp_path / name).exists() for name in (
        "tmprecent.nc", "other.nc", "tmpother.txt", "nested/tmpold.nc", "tmplink.nc"
    ))
