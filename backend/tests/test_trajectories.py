from datetime import datetime, timezone

from app.ingest.igra import parse_soundings
from app.processing.trajectories import backward_points, wind_at_pressure


def test_backward_eastward_wind_moves_west():
    points = backward_points(-3, -55, 10, 0, 1)
    assert points[-1]['lon'] < -55
    assert points[-1]['age'] == -1


def test_interpolation_and_no_extrapolation():
    levels = [dict(pressure=900, u=10, v=2), dict(pressure=1000, u=-10, v=4)]
    assert wind_at_pressure(levels, 950) == (0, 3)
    assert wind_at_pressure(levels, 850) is None


def test_igra_units_and_missing_wind():
    header = '#BRM00082281 2026 11 17 12'
    row = list(' ' * 51)
    row[9:15] = ' 92500'
    row[40:45] = '   90'
    row[46:51] = '  100'
    content = header + '\n' + ''.join(row)
    profiles = parse_soundings(content, 'BRM00082281', datetime(2026, 1, 1, tzinfo=timezone.utc))
    wind = profiles[0]['levels'][0]
    assert wind['pressure'] == 925
    assert abs(wind['u'] + 10) < 1e-8
    assert abs(wind['v']) < 1e-8
    row[46:51] = '-9999'
    assert parse_soundings(header + '\n' + ''.join(row), 'BRM00082281', datetime(2026, 1, 1, tzinfo=timezone.utc)) == []
