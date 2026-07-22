RAW TELEMETRY SAMPLE
==================================================
Driver:    ANT
Lap:       68.0 (fastest lap of session)
Rows:      552 total, 500 shown
==================================================

COLUMNS IN RAW TELEMETRY:
--------------------------------------------------
  Date                       dtype=datetime64[ns]   sample=2026-05-24 21:36:49.566000
  SessionTime                dtype=timedelta64[ns]  sample=0 days 02:29:34.092000
  DriverAhead                dtype=object           sample=
  DistanceToDriverAhead      dtype=float64          sample=nan
  Time                       dtype=timedelta64[ns]  sample=0 days 00:00:00
  RPM                        dtype=float64          sample=10827.4249888
  Speed                      dtype=float64          sample=283.0
  nGear                      dtype=int64            sample=7
  Throttle                   dtype=float64          sample=100.0
  Brake                      dtype=bool             sample=False
  DRS                        dtype=int64            sample=0
  Source                     dtype=object           sample=interpolation
  Distance                   dtype=float64          sample=-0.00017740723308046213
  RelativeDistance           dtype=float64          sample=-4.0660638344464616e-08
  Status                     dtype=object           sample=OnTrack
  X                          dtype=float64          sample=3354.1647465777733
  Y                          dtype=float64          sample=920.2529471207254
  Z                          dtype=float64          sample=133.68778673752846

Key columns explained:
  - X, Y:          Car coordinates on track (metres)
  - Speed:         Car speed (km/h)
  - Throttle:      Throttle application (0-100%%)
  - Brake:         Brake application (True/False or 0-100)
  - nGear:         Current gear number
  - RPM:           Engine RPM
  - DRS:           DRS status (0-14, >10 means open)
  - Distance:      Distance covered in this lap (metres)
  - SessionTime:   Time elapsed since session start
