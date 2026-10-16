"""Hand-made scenarios. SIMULATED -- not live NOAA data."""

STORM_SNAPSHOT = {
    "simulated": True,
    "scales": {"G": 3, "S": 2, "R": 1},
    "kp": {"value": 7},
    "dst": {"value": -120},
    "solar_wind_speed": {"km_s": 620},
    "bz": {"nT": -12},
    "proton": {"flux_ge10MeV": 150},
}