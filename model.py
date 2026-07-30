"""
Thermal model of a timber chalet in Zinal (Val d'Anniviers, Valais, Switzerland).

The site is described at village resolution only: a 1 km grid point at
46.13 N / 7.63 E, ~1680 m, on the east flank of the valley. Everything here is
generic to that setting -- the building dimensions below are a typical 1960s-70s
Anniviers chalet, not a survey of any particular house.

Data sources (downloaded into ./data/):
- horizon.json  : PVGIS DEM-calculated horizon profile (mountain shading)
- tmy.json      : PVGIS Typical Meteorological Year, hourly (T, DNI, DHI, GHI, wind)
- archive.json  : Open-Meteo ERA5 daily mean temperature 2015-2025 (valley grid cell)
- climate.json  : Open-Meteo CMIP6-HighRes daily mean temperature 2026-2050 (3 models)
- climate_minmax.json : same source, daily max/min -> separate day & night warming trends

Terrain: ~1680 m, slope ~21.5 % falling to the west (east flank of the valley)

Roof pitch: Anniviers RCCZ (Oct 2024), Art. 109: two regular pans, slope 40-50 %.
We use 45 % = 24.2 degrees. The ridge runs E-W -> the two pans face SOUTH and NORTH.
The house is one full storey plus a single attic room under the roof.
"""

import json
import math
import os
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ----------------------------------------------------------------------------- site
LAT = 46.13              # deg N, village grid point (1 km resolution)
LON = 7.63               # deg E
ALT = 1681.0             # m at that grid point
TERRAIN_SLOPE_E = 0.2145 # dz/dx toward east (terrain rises east)
TERRAIN_SLOPE_N = 0.037  # dz/dy toward north

# ----------------------------------------------------------------------------- geometry
# Exterior rectangle: 10 m (N-S) x 6 m (E-W).
# Ridge runs E-W: pans face S and N, gable triangles sit on the long E/W walls.
# One full storey; the second floor is a single attic room under the roof.
LEN_NS = 10.0                      # typical Anniviers chalet footprint
LEN_EW = 6.0
EAVES_H = 2.7                      # m, one storey + floor build-up
ROOF_PITCH = math.atan(0.45)       # 24.2 deg (RCCZ Art.109: 40-50 %)
RIDGE_H = EAVES_H + (LEN_NS / 2) * 0.45   # 4.95 m (pans span the 10 m N-S depth)
FLOOR_AREA = 72.0                  # m2 heated (ground 52 + one attic room ~20)
VOLUME = 175.0                     # m3 heated (ground + attic space under roof)

# Windows: 3 on the first floor (2 west + 1 south, ~1.4 m2 each),
# 1 in the attic room (west gable, valley view, ~1.0 m2)
A_WIN_W = 2 * 1.4 + 1.0            # m2 west facade + west gable
A_WIN_S = 1.4                      # m2 south facade
A_WIN = A_WIN_W + A_WIN_S          # 5.2 m2

A_WALL = (2 * (LEN_NS + LEN_EW) * EAVES_H            # 86.4
          + 2 * 0.5 * LEN_NS * (RIDGE_H - EAVES_H)   # 2 E/W gable triangles: 22.5
          - A_WIN)                                   # = 103.7 m2
A_ROOF = 2 * LEN_EW * (LEN_NS / 2) / math.cos(ROOF_PITCH)  # 65.8 m2 total
A_ROOF_PAN = A_ROOF / 2                                    # 32.9 m2 south (or north) pan
A_FLOOR = LEN_NS * LEN_EW                                  # 60 m2 on cellar/ground

# ----------------------------------------------------------------------------- fabric
# Wall: 13 cm wood (lambda 0.13) + 7 cm glass wool (lambda 0.038), Rsi 0.13 Rse 0.04
U_WALL = 1 / (0.13 + 0.13 / 0.13 + 0.07 / 0.038 + 0.04)      # 0.33 W/m2K
# Roof: 13 cm wood + 20 cm glass wool, Rsi 0.10 Rse 0.04
U_ROOF = 1 / (0.10 + 0.13 / 0.13 + 0.20 / 0.038 + 0.04)      # 0.16 W/m2K
U_WIN = 2.8          # 1960s-70s double glazing
G_WIN = 0.70         # solar factor of the glazing
WIN_EFF = 0.75 * 0.9 # frame fraction x dirt/curtain factor on solar gains
U_FLOOR = 0.8        # timber floor over cellar
B_FLOOR = 0.6        # SIA reduction factor: cellar/ground is milder than outside
ACH = 0.45           # air changes per hour (older envelope, closed up)

H_TRANS = (A_WALL * U_WALL + A_ROOF * U_ROOF + A_WIN * U_WIN
           + A_FLOOR * U_FLOOR * B_FLOOR)                    # W/K
H_VENT = ACH * VOLUME * 0.34                                 # W/K
H_TOT = H_TRANS + H_VENT                                     # ~115 W/K

# Light timber construction; interior lining sits inboard of the insulation,
# so effective accessible mass is modest.
C_EFF = 4.0 * 3.6e6  # J/K  (4.0 kWh/K -> time constant ~ 35 h)

# ----------------------------------------------------------------------------- energy prices & systems
ELEC_PRICE = 0.27        # CHF/kWh (Sierre-Energie region, incl. grid & taxes)
FEED_IN = 0.10           # CHF/kWh PV export
WOOD_PRICE_STERE = 140.0 # CHF/stere delivered
WOOD_KWH_STERE = 1700.0  # kWh primary per stere (dry hardwood/larch mix)
STOVE_EFF = 0.70
CAP_ELECTRIC = 6000.0    # W (three 2 kW heaters)
CAP_STOVE = 8000.0       # W
CAP_HP_NOM = 6000.0      # W thermal, air-source
DHW_KWH_DAY = 3.0        # kWh/day hot water when occupied (electric boiler exists)

# Pellet stove: programmable (thermostat + timer), covers frost guard AND comfort
CAP_PELLET = 8000.0      # W thermal
PELLET_EFF = 0.87        # combustion efficiency
PELLET_KWH_KG = 4.8      # kWh per kg pellets
PELLET_PRICE_KG = 0.48   # CHF/kg (bags, delivered ~480 CHF/t)
PELLET_EL_RUN = 100.0    # W electrical while burning (auger, fans, control)
PELLET_EL_IGN = 500.0    # W electrical during ignition ...
PELLET_IGN_H = 0.25      # ... for 15 minutes at each cold start

# PV on the roof: 425 Wp glass-glass modules, 1.72 x 1.13 m.
# One pan is 6.0 m (ridge) x 5.48 m (slope): 5 portrait columns x 3 rows = 15 modules.
PV_MOD_KWP = 0.425
PV_MOD_PER_PAN = 15
PV_KWP_PAN = PV_MOD_PER_PAN * PV_MOD_KWP   # 6.4 kWp per pan (south or north)
PV_PR = 0.80                               # inverter, temp, wiring, soiling/snow avg

def hp_cop(t_out):
    """Air-air split heat pump COP vs outdoor temp (datasheet-shaped, conservative)."""
    return np.clip(3.0 + 0.07 * t_out, 1.8, 4.6)

def hp_capacity(t_out):
    """Thermal capacity derating in deep cold."""
    return CAP_HP_NOM * np.clip(1 + 0.025 * np.minimum(t_out + 7, 0), 0.55, 1.0)

# ============================================================================= weather
def _obs_monthly_means(y0=2015, y1=2025):
    """Observed ERA5 monthly mean T (degC) for the valley, elevation-corrected."""
    with open(os.path.join(DATA, "archive.json")) as f:
        d = json.load(f)["daily"]
    sums = np.zeros(12); cnt = np.zeros(12)
    for t, v in zip(d["time"], d["temperature_2m_mean"]):
        if v is None:
            continue
        y, m = int(t[:4]), int(t[5:7])
        if y0 <= y <= y1:
            sums[m - 1] += v; cnt[m - 1] += 1
    return sums / cnt

def load_tmy():
    """Return dict of hourly arrays (8760): month, day, hour(UTC), t2m, ghi, dni, dhi, wind.

    PVGIS TMY T2m comes from a coarse ERA5 grid cell centred well above the
    valley floor and runs several K too cold. Each month's mean is therefore
    corrected onto the ERA5 elevation-corrected observation for the valley
    (2015-2025); the TMY keeps its hourly structure and its (satellite-based,
    trustworthy) irradiance. Temperatures then represent ~2020 climate.
    """
    with open(os.path.join(DATA, "tmy.json")) as f:
        rows = json.load(f)["outputs"]["tmy_hourly"]
    out = {k: np.empty(len(rows)) for k in
           ("month", "day", "hour", "t2m", "ghi", "dni", "dhi", "wind")}
    for i, r in enumerate(rows):
        ts = r["time(UTC)"]                      # e.g. 20160101:0000
        out["month"][i] = int(ts[4:6])
        out["day"][i] = int(ts[6:8])
        out["hour"][i] = int(ts[9:11])
        out["t2m"][i] = r["T2m"]
        out["ghi"][i] = r["G(h)"]
        out["dni"][i] = r["Gb(n)"]
        out["dhi"][i] = r["Gd(h)"]
        out["wind"][i] = r["WS10m"]
    # day of year (non-leap)
    cum = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30])
    out["doy"] = cum[out["month"].astype(int) - 1] + out["day"]
    m = out["month"].astype(int)
    raw_monthly = np.array([out["t2m"][m == k].mean() for k in range(1, 13)])
    out["t2m"] = out["t2m"] + (_obs_monthly_means() - raw_monthly)[m - 1]
    return out

TMY_CENTER_YEAR = 2020.0   # temperatures are anchored on ERA5 obs 2015-2025

def _monthly_year_means(times, values):
    """(12, n_years) array of monthly means and the year vector."""
    years = sorted({int(t[:4]) for t in times})
    yi = {y: j for j, y in enumerate(years)}
    sums = np.zeros((12, len(years))); cnt = np.zeros((12, len(years)))
    for t, v in zip(times, values):
        if v is None:
            continue
        m, j = int(t[5:7]) - 1, yi[int(t[:4])]
        sums[m, j] += v; cnt[m, j] += 1
    return sums / np.maximum(cnt, 1), np.array(years, float)

def monthly_warming_slopes():
    """Per-month linear warming trends (K/yr), CMIP6-HighRes 3-model mean 2026-2050.

    Returns {'mean','day','night'}: 12 monthly slopes each. 'day' fits the daily-max
    series, 'night' the daily-min (days and nights do not warm at the same rate).
    Model bias cancels because only the slope is used; beyond 2050 the linear
    trend is extrapolated.
    """
    with open(os.path.join(DATA, "climate.json")) as f:
        mean_d = json.load(f)["daily"]
    with open(os.path.join(DATA, "climate_minmax.json")) as f:
        mm_d = json.load(f)["daily"]
    out = {}
    for kind, daily, stem in (("mean", mean_d, "temperature_2m_mean"),
                              ("day", mm_d, "temperature_2m_max"),
                              ("night", mm_d, "temperature_2m_min")):
        models = [k for k in daily if k.startswith(stem)]
        per_year = np.mean([_monthly_year_means(daily["time"], daily[k])[0]
                            for k in models], axis=0)
        years = _monthly_year_means(daily["time"], daily[models[0]])[1]
        out[kind] = np.array([np.polyfit(years, per_year[m], 1)[0] for m in range(12)])
    return out

def apply_warming(w, year, slopes=None):
    """Copy of the weather dict with temperatures shifted to `year`'s climate.

    Hours with the sun up get the daytime (daily-max) trend, night hours the
    nighttime (daily-min) trend, month by month. The TMY represents ~2014, so
    even 'now' gets a small positive shift.
    """
    if slopes is None:
        slopes = monthly_warming_slopes()
    el, _ = sun_position(w["doy"], w["hour"])
    m = w["month"].astype(int) - 1
    dt_years = year - TMY_CENTER_YEAR
    delta = np.where(el > 0, slopes["day"][m], slopes["night"][m]) * dt_years
    w2 = dict(w)
    w2["t2m"] = w["t2m"] + delta
    return w2

def day_night_monthly(w):
    """Monthly mean day (sun up) and night temperatures, plus annual means."""
    el, _ = sun_position(w["doy"], w["hour"])
    day = el > 0
    m = w["month"].astype(int)
    t = w["t2m"]
    day_m = np.array([t[(m == k) & day].mean() for k in range(1, 13)])
    night_m = np.array([t[(m == k) & ~day].mean() for k in range(1, 13)])
    return day_m, night_m, float(t[day].mean()), float(t[~day].mean())

# ============================================================================= solar geometry
def sun_position(doy, hour_utc):
    """Solar elevation & compass azimuth (deg, N=0 E=90) for arrays. Mid-hour."""
    n = np.asarray(doy, dtype=float)
    B = 2 * math.pi * (n - 1) / 365.0
    decl = (0.006918 - 0.399912 * np.cos(B) + 0.070257 * np.sin(B)
            - 0.006758 * np.cos(2 * B) + 0.000907 * np.sin(2 * B)
            - 0.002697 * np.cos(3 * B) + 0.00148 * np.sin(3 * B))       # rad
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(B) - 0.032077 * np.sin(B)
                    - 0.014615 * np.cos(2 * B) - 0.04089 * np.sin(2 * B))  # minutes
    tst = np.asarray(hour_utc, dtype=float) + 0.5 + LON / 15.0 + eot / 60.0
    omega = np.radians(15.0 * (tst - 12.0))
    lat = math.radians(LAT)
    sin_el = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(omega)
    el = np.degrees(np.arcsin(np.clip(sin_el, -1, 1)))
    cos_az = ((np.sin(decl) - sin_el * math.sin(lat))
              / np.maximum(np.cos(np.radians(el)) * math.cos(lat), 1e-9))
    az0 = np.degrees(np.arccos(np.clip(cos_az, -1, 1)))   # 0..180 from north
    az = np.where(omega <= 0, az0, 360.0 - az0)           # morning east, afternoon west
    return el, az

def load_horizon():
    """Horizon elevation (deg) as a function of compass azimuth, callable."""
    with open(os.path.join(DATA, "horizon.json")) as f:
        prof = json.load(f)["outputs"]["horizon_profile"]
    # PVGIS: A=0 south, -90 east, +90 west  ->  compass = A + 180
    az = np.array([(p["A"] + 180.0) % 360.0 for p in prof])
    h = np.array([p["H_hor"] for p in prof])
    order = np.argsort(az)
    az, h = az[order], h[order]
    az = np.concatenate([[az[-1] - 360], az, [az[0] + 360]])   # wrap
    h = np.concatenate([[h[-1]], h, [h[0]]])
    return lambda a: np.interp(np.asarray(a) % 360.0, az, h)

def sky_view_factor(horizon):
    a = np.linspace(0, 360, 361)
    return float(np.mean(np.cos(np.radians(horizon(a))) ** 2))

def poa_irradiance(el, az, dni, dhi, ghi, tilt, surf_az, horizon, svf, albedo):
    """Plane-of-array irradiance W/m2 with horizon masking of the beam (isotropic sky)."""
    elr, tr = np.radians(el), math.radians(tilt)
    cos_inc = (np.sin(elr) * math.cos(tr)
               + np.cos(elr) * math.sin(tr) * np.cos(np.radians(az - surf_az)))
    visible = el > horizon(az)                       # mountains block the beam
    beam = dni * np.clip(cos_inc, 0, None) * visible * (el > 0)
    sky = dhi * (1 + math.cos(tr)) / 2 * svf
    ground = ghi * albedo * (1 - math.cos(tr)) / 2
    return beam + sky + ground

def snow_albedo(month):
    """Ground albedo: snow cover Nov-Apr at this altitude."""
    return np.where(np.isin(month, (11, 12, 1, 2, 3, 4)), 0.6, 0.2)

# ============================================================================= building
def solar_gains(w, horizon, svf, a_win_w=A_WIN_W, a_win_s=A_WIN_S,
                g_win=G_WIN, win_eff=WIN_EFF):
    """Hourly solar heat gain through the windows, W."""
    el, az = sun_position(w["doy"], w["hour"])
    alb = snow_albedo(w["month"])
    poa_w = poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"], 90, 270, horizon, svf, alb)
    poa_s = poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"], 90, 180, horizon, svf, alb)
    return (a_win_w * poa_w + a_win_s * poa_s) * g_win * win_eff, el, az

def simulate(w, q_solar, occupied, setpoint_occ=20.0, setpoint_abs=None,
             capacity=None, preheat_h=12, t0=5.0,
             h_tot=None, c_eff=None, q_int_occ=250.0, q_int_abs=10.0):
    """Single-node RC simulation over the year.

    occupied     : bool array (8760)
    setpoint_abs : frost-guard setpoint when absent (None = no heating when absent)
    capacity     : heater capacity in W (scalar or array), None = unlimited
    h_tot, c_eff : override the module-level fabric constants (for the dashboard)
    Returns dict with indoor temp and heating power arrays.
    """
    H = H_TOT if h_tot is None else h_tot
    C = C_EFF if c_eff is None else c_eff
    n = len(q_solar)
    dt = 3600.0
    tin = np.empty(n); q_heat = np.zeros(n)
    t = t0
    # pre-heat: allow comfort setpoint a few hours before arrival
    occ_pre = occupied.copy()
    idx = np.where(occupied)[0]
    for i in idx:
        occ_pre[max(0, i - preheat_h):i] = True
    q_int = np.where(occupied, q_int_occ, q_int_abs)   # people/cooking vs standby
    cap = np.broadcast_to(np.asarray(capacity if capacity is not None else np.inf), (n,))
    for i in range(n):
        gain = q_solar[i] + q_int[i]
        t_free = t + dt / C * (gain - H * (t - w["t2m"][i]))
        sp = setpoint_occ if occ_pre[i] else setpoint_abs
        if sp is not None and t_free < sp:
            need = (sp - t_free) * C / dt
            q_heat[i] = min(need, cap[i])
            t_free += q_heat[i] * dt / C
        t = t_free
        tin[i] = t
    return {"tin": tin, "q_heat": q_heat}

def simulate_offgrid(w, q_solar, occupied, pv_w, aux_w,
                     setpoint_occ=20.0, setpoint_abs=None, capacity=None,
                     heat_mode="direct", cop_arr=None, hpcap_arr=None,
                     batt_kwh=10.0, p_max=3000.0, eff=0.92,
                     preheat_h=12, t0=5.0, h_tot=None, c_eff=None,
                     q_int_occ=250.0, q_int_abs=10.0,
                     pel_run=PELLET_EL_RUN, pel_ign=PELLET_EL_IGN,
                     pel_ign_h=PELLET_IGN_H):
    """Coupled thermal + PV/battery simulation with NO grid connection.

    heat_mode: 'none'        heat needs no electricity (wood stove)
               'direct'      electric heating, 1 kWh el = 1 kWh heat
               'hp'          heat pump (cop_arr, hpcap_arr) + resistance backup
               'direct_away' stove when present, electric frost guard when away
                             (only the away part needs power)
               'pellet'      pellet stove: fuel gives the heat, but the electronics
                             need PELLET_EL_RUN while burning plus an ignition
                             surge (PELLET_EL_IGN for PELLET_IGN_H) at each start;
                             without that power the stove will not light
    aux_w : non-heating electric load (plugs + DHW), served FIRST; shedding it
            does not affect temperature. Heating gets the remaining power.
    Surplus PV charges the battery; the rest is curtailed (no export).
    Returns dict: tin, q_heat (delivered), ser (hourly W arrays: pv_direct,
    batt_charge, batt_discharge, curtailed, unserved_aux, unserved_heat_el,
    heat_el, soc).
    """
    H = H_TOT if h_tot is None else h_tot
    C = C_EFF if c_eff is None else c_eff
    n = len(q_solar)
    dt = 3600.0
    occ_pre = occupied.copy()
    for i in np.where(occupied)[0]:
        occ_pre[max(0, i - preheat_h):i] = True
    q_int = np.where(occupied, q_int_occ, q_int_abs)
    cap = np.broadcast_to(np.asarray(capacity if capacity is not None else np.inf), (n,))
    sq = math.sqrt(eff)
    batt = batt_kwh * 1000.0
    soc = 0.0
    tin = np.empty(n); q_heat = np.zeros(n)
    ser = {k: np.zeros(n) for k in
           ("pv_direct", "batt_charge", "batt_discharge", "curtailed",
            "unserved_aux", "unserved_heat_el", "heat_el", "soc")}
    t = t0
    burning = False          # pellet stove state, for ignition-surge accounting
    for i in range(n):
        pv = pv_w[i]
        dis_budget = p_max
        # --- non-heating load first
        aux = aux_w[i]
        direct = min(pv, aux)
        pv -= direct
        dis = min((aux - direct) / sq, dis_budget, soc)
        soc -= dis; dis_budget -= dis
        ser["pv_direct"][i] += direct
        ser["batt_discharge"][i] += dis * sq
        ser["unserved_aux"][i] = aux - direct - dis * sq
        # --- thermal free-float and heating need
        gain = q_solar[i] + q_int[i]
        t_free = t + dt / C * (gain - H * (t - w["t2m"][i]))
        sp = setpoint_occ if occ_pre[i] else setpoint_abs
        need = 0.0
        if sp is not None and t_free < sp:
            need = min((sp - t_free) * C / dt, cap[i])
        # electricity that heat requires
        stove_hour = heat_mode == "none" or (heat_mode == "direct_away" and occ_pre[i])
        pellet_hour = heat_mode == "pellet"
        if stove_hour:
            e_req = 0.0
        elif pellet_hour:
            # auxiliaries only: running draw + ignition surge if it must (re)light
            e_req = (pel_run + (0.0 if burning else (pel_ign - pel_run) * pel_ign_h)
                     ) if need > 0 else 0.0
        elif heat_mode == "hp":
            need = min(need, hpcap_arr[i])   # HP thermal cap; no resistance backup off-grid
            e_req = need / cop_arr[i]
        else:
            e_req = need
        # serve heating with what remains
        heat = need if stove_hour else 0.0
        if e_req > 0:
            direct = min(pv, e_req)
            pv -= direct
            dis = min((e_req - direct) / sq, dis_budget, soc)
            soc -= dis; dis_budget -= dis
            e_served = direct + dis * sq
            if pellet_hour:
                # the burner is all-or-nothing: no auxiliary power, no fire
                lit = e_served >= e_req - 1e-6
                heat = need if lit else 0.0
                burning = lit
            else:
                heat = need * (e_served / e_req)
            ser["pv_direct"][i] += direct
            ser["batt_discharge"][i] += dis * sq
            ser["heat_el"][i] = e_served
            ser["unserved_heat_el"][i] = e_req - e_served
        elif pellet_hour:
            burning = False          # no heat demand this hour: the burner shuts down
        # surplus PV -> battery, rest curtailed
        chg = min(pv, p_max, (batt - soc) / sq)
        soc += chg * sq
        ser["batt_charge"][i] = chg
        ser["curtailed"][i] = pv - chg
        ser["soc"][i] = soc
        q_heat[i] = heat
        t = t_free + heat * dt / C
        tin[i] = t
    return {"tin": tin, "q_heat": q_heat, "ser": ser}

if __name__ == "__main__":
    print(f"H_trans={H_TRANS:.0f} W/K  H_vent={H_VENT:.0f} W/K  H_tot={H_TOT:.0f} W/K")
    print(f"U wall={U_WALL:.2f} roof={U_ROOF:.2f}  A wall={A_WALL:.0f} roof={A_ROOF:.0f} m2"
          f" ({A_ROOF_PAN:.1f} per pan)")
    print(f"time constant = {C_EFF / H_TOT / 3600:.0f} h")
    w = load_tmy()
    hz = load_horizon()
    print(f"SVF = {sky_view_factor(hz):.2f}")
    s = monthly_warming_slopes()
    for k in ("mean", "day", "night"):
        print(f"warming slope {k:>5}: annual {np.mean(s[k]) * 10:.2f} K/decade, "
              f"monthly K/decade {np.round(s[k] * 10, 2)}")
