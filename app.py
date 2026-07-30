"""Interactive dashboard for the Zinal chalet thermal model.

Run:  streamlit run app.py

- hourly indoor + outdoor temperature over the year, for climate horizons
  2026 / 2036 / 2046 / 2056 / 2066 / 2076
- daily view: per-day mean with +/-1, 2, 3 sigma bands (spread of the 24 hourly
  values within each day)
- every assumption is editable in the sidebar; scenarios toggle on/off and
  update the indoor temperature; presence periods are user-defined
"""
import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import carbon as CB
import model as M
import scene3d
import simulate as S

st.set_page_config(page_title="Zinal chalet model", page_icon="🏔️", layout="wide")

# ------------------------------------------------------------------ palette
INK2 = "#52514e"
OUTSIDE_C = "#898781"
SCEN_COLORS = {
    "A — no heating (free-float)": "#2a78d6",
    "B — electric heaters": "#eb6834",
    "C — wood stove only": "#8a63d2",
    "C2 — wood + electric frost guard": "#1baf7a",
    "P — pellet stove (programmed: comfort + frost guard)": "#d6567d",
    "E — air-source heat pump": "#eda100",
}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DEFAULT_PERIODS = [("2026-12-24", "2026-01-04"),   # Christmas (wraps year end)
                   ("2026-02-08", "2026-02-15"),   # February week
                   ("2026-07-15", "2026-08-05")]   # summer holidays

def rgba(hex_c, a):
    h = hex_c.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"

# ------------------------------------------------------------------ cached data
@st.cache_resource
def geo():
    hz = M.load_horizon()
    return hz, M.sky_view_factor(hz)

@st.cache_data(show_spinner=False)
def tmy():
    return M.load_tmy()

@st.cache_data(show_spinner=False)
def warming_slopes():
    return M.monthly_warming_slopes()

@st.cache_data(show_spinner=False)
def weather(year):
    return M.apply_warming(tmy(), year, warming_slopes())

@st.cache_data(show_spinner=False)
def poa_surfaces():
    """Irradiance on the window planes and the two roof pans (W/m2, TMY)."""
    w = tmy()
    hz, svf = geo()
    el, az = M.sun_position(w["doy"], w["hour"])
    alb = M.snow_albedo(w["month"])
    args = (el, az, w["dni"], w["dhi"], w["ghi"])
    tilt = float(np.degrees(M.ROOF_PITCH))
    return dict(
        win_w=M.poa_irradiance(*args, 90, 270, hz, svf, alb),
        win_s=M.poa_irradiance(*args, 90, 180, hz, svf, alb),
        roof_s=M.poa_irradiance(*args, tilt, 180, hz, svf, alb),
        roof_n=M.poa_irradiance(*args, tilt, 0, hz, svf, alb),
    )

@st.cache_data(show_spinner=False)
def occupancy_array(periods, wknd_on, every_other, months):
    """Presence from explicit periods + a weekend rule (template year starts Monday)."""
    w = tmy()
    doy = w["doy"].astype(int)
    occ = np.zeros(len(doy), bool)
    for a, b in periods:
        d0 = dt.date.fromisoformat(a).timetuple().tm_yday
        d1 = dt.date.fromisoformat(b).timetuple().tm_yday
        occ |= ((doy >= d0) & (doy <= d1)) if d1 >= d0 else ((doy >= d0) | (doy <= d1))
    if wknd_on and months:
        weekday = (doy - 1) % 7
        week = (doy - 1) // 7
        sel = np.isin(weekday, (5, 6)) & np.isin(w["month"].astype(int), months)
        if every_other:
            sel &= week % 2 == 0
        occ |= sel
    return occ

@st.cache_data(show_spinner=False)
def run_sim(year, occ_spec, sp_occ, sp_abs, capacity, preheat,
            h_tot, c_eff, aw, a_s, g, weff, q_occ, q_abs):
    w = weather(year)
    occ = occupancy_array(*occ_spec)
    poa = poa_surfaces()
    q_sol = (aw * poa["win_w"] + a_s * poa["win_s"]) * g * weff
    r = M.simulate(w, q_sol, occ, setpoint_occ=sp_occ, setpoint_abs=sp_abs,
                   capacity=capacity, preheat_h=int(preheat),
                   h_tot=h_tot, c_eff=c_eff, q_int_occ=q_occ, q_int_abs=q_abs)
    return r["tin"], r["q_heat"]

@st.cache_data(show_spinner=False)
def battery_series(pv_w, load_w, cap_kwh, p_max_w, eff):
    """(grid_import_kWh, export_kWh, self_cons_kWh, dict of hourly arrays)."""
    return S.battery_dispatch(pv_w, load_w, cap_kwh, p_max_w, eff, return_series=True)

@st.cache_data(show_spinner=False)
def run_sim_offgrid(year, occ_spec, sp_occ, sp_abs, cap, heat_mode, preheat,
                    h_tot, c_eff, aw, a_s, g, weff, q_occ, q_abs,
                    kwp, kwp_pan_, pv_pr_, batt_kwh_, batt_kw_, batt_eff_,
                    dhw_kwh_, base_occ_, base_abs_,
                    cap_hp_, cop0_, cop_slope_, cop_min_, cop_max_,
                    pel_run_, pel_ign_, pel_ign_h_):
    w = weather(year)
    occ = occupancy_array(*occ_spec)
    poa = poa_surfaces()
    q_sol = (aw * poa["win_w"] + a_s * poa["win_s"]) * g * weff
    if kwp == 0:
        pv = np.zeros(8760)
    elif kwp <= kwp_pan_:
        pv = kwp * poa["roof_s"] * pv_pr_
    else:
        pv = kwp_pan_ * (poa["roof_s"] + poa["roof_n"]) * pv_pr_
    aux = np.where(occ, base_occ_, base_abs_).astype(float)
    aux[occ & (w["hour"] >= 11) & (w["hour"] < 17)] += dhw_kwh_ * 1000.0 / 6.0
    cop_arr = np.clip(cop0_ + cop_slope_ * w["t2m"], cop_min_, cop_max_)
    hpcap_arr = cap_hp_ * np.clip(1 + 0.025 * np.minimum(w["t2m"] + 7, 0), 0.55, 1.0)
    r = M.simulate_offgrid(w, q_sol, occ, pv, aux,
                           setpoint_occ=sp_occ, setpoint_abs=sp_abs, capacity=cap,
                           heat_mode=heat_mode, cop_arr=cop_arr, hpcap_arr=hpcap_arr,
                           batt_kwh=batt_kwh_, p_max=batt_kw_ * 1000, eff=batt_eff_,
                           preheat_h=int(preheat), h_tot=h_tot, c_eff=c_eff,
                           q_int_occ=q_occ, q_int_abs=q_abs,
                           pel_run=pel_run_, pel_ign=pel_ign_, pel_ign_h=pel_ign_h_)
    return r["tin"], r["q_heat"], r["ser"]

@st.cache_resource
def scene_fig():
    return scene3d.build_scene()

# ------------------------------------------------------------------ sidebar
ASSUM = []   # (name, value, unit) — rebuilt on every rerun, echoed in a table

def num(label, default, unit="", key=None, **kw):
    """Editable assumption. `key` lets a field re-seed when its preset changes."""
    v = st.number_input(f"{label}" + (f"  ({unit})" if unit else ""),
                        value=float(default), key=key or f"in_{label}", **kw)
    ASSUM.append((label, v, unit))
    return v

with st.sidebar:
    st.title("🏔️ Zinal chalet")

    year = st.select_slider("Climate horizon",
                            options=[2026, 2036, 2046, 2056, 2066, 2076], value=2026)

    st.subheader("Scenarios (indoor temperature)")
    enabled = [name for name in SCEN_COLORS
               if st.checkbox(name, value=name.startswith(("A", "E", "P")),
                              key=f"sc_{name}")]
    pv_option = st.radio("PV on the roof (with the heat pump)",
                         ["none", "half roof (south pan)", "full roof (both pans)"],
                         index=1, help="Changes costs, not the indoor temperature "
                                       "(unless off-grid).")
    offgrid = st.checkbox("🔌 off-grid — PV + battery only, no grid",
                          value=False,
                          help="Grid import/export disabled. Electric heating "
                               "(B, C2's frost guard, E heat pump) only runs when "
                               "PV + battery can power it — otherwise the house "
                               "drifts cold. Pellet and wood heating keep working.")

    st.subheader("Presence in the house")
    st.session_state.setdefault("periods", list(DEFAULT_PERIODS))
    st.caption("**Periods** (edit or remove; a period may wrap the year end):")
    for i, (a, b) in enumerate(st.session_state.periods):
        ca, cb = st.columns([4, 1])
        ca.markdown(f"• {a[5:]} → {b[5:]}" + ("  *(wraps)*" if b < a else ""))
        if cb.button("✕", key=f"rm_{i}", help="remove this period"):
            st.session_state.periods.pop(i)
            st.rerun()
    c1, c2 = st.columns(2)
    d_from = c1.date_input("from", dt.date(2026, 1, 1),
                           min_value=dt.date(2026, 1, 1), max_value=dt.date(2026, 12, 31))
    d_to = c2.date_input("to", dt.date(2026, 1, 7),
                         min_value=dt.date(2026, 1, 1), max_value=dt.date(2026, 12, 31))
    if st.button("➕ add period", width="stretch"):
        st.session_state.periods.append((d_from.isoformat(), d_to.isoformat()))
        st.rerun()
    st.caption("**Weekends:**")
    wknd_on = st.checkbox("weekends at the chalet", value=True)
    wknd_freq = st.selectbox("which weekends", ["every other weekend", "every weekend"],
                             index=0, disabled=not wknd_on)
    wknd_months = st.multiselect("in months", MONTH_NAMES,
                                 default=["Jan", "Feb", "Mar", "Apr", "Sep", "Oct", "Dec"],
                                 disabled=not wknd_on)
    occ_spec = (tuple(st.session_state.periods), wknd_on,
                wknd_freq == "every other weekend",
                tuple(MONTH_NAMES.index(m) + 1 for m in wknd_months))

    st.subheader("Assumptions")
    with st.expander("Comfort"):
        sp_occ = num("comfort setpoint when present", 20.0, "°C", step=0.5)
        sp_frost = num("frost guard when away", 7.0, "°C", step=0.5)
        preheat = num("pre-heat before arrival", 12, "h", step=1.0)
    with st.expander("Building fabric"):
        u_wall = num("U wall", M.U_WALL, "W/m²K", step=0.01, format="%.2f")
        u_roof = num("U roof", M.U_ROOF, "W/m²K", step=0.01, format="%.2f")
        u_win = num("U window", M.U_WIN, "W/m²K", step=0.1)
        u_floor = num("U floor", M.U_FLOOR, "W/m²K", step=0.1)
        ach = num("infiltration", M.ACH, "air changes/h", step=0.05, format="%.2f")
        c_eff_kwh = num("thermal mass", 4.0, "kWh/K", step=0.5)
    with st.expander("Windows & internal gains"):
        aw = num("window area west (incl. gable)", M.A_WIN_W, "m²", step=0.1)
        a_s = num("window area south", M.A_WIN_S, "m²", step=0.1)
        g_win = num("glazing solar factor g", M.G_WIN, "", step=0.05, format="%.2f")
        win_eff = num("frame + dirt factor on solar gains", M.WIN_EFF, "", step=0.05,
                      format="%.2f")
        q_occ = num("internal gains when present", 250.0, "W", step=50.0)
        q_abs = num("internal gains when away", 10.0, "W", step=5.0)
    with st.expander("Heating systems"):
        pel_el_run = num("pellet stove electronics while burning", M.PELLET_EL_RUN, "W",
                         step=10.0)
        pel_el_ign = num("pellet stove ignition draw", M.PELLET_EL_IGN, "W", step=50.0)
        pel_ign_min = num("ignition duration", M.PELLET_IGN_H * 60, "min", step=5.0)
        cap_elec = num("electric heaters capacity", M.CAP_ELECTRIC, "W", step=500.0)
        cap_stove = num("wood stove capacity", M.CAP_STOVE, "W", step=500.0)
        stove_eff = num("stove efficiency", M.STOVE_EFF, "", step=0.05, format="%.2f")
        cap_pel = num("pellet stove capacity", M.CAP_PELLET, "W", step=500.0)
        pel_eff = num("pellet stove efficiency", M.PELLET_EFF, "", step=0.01, format="%.2f")
        pel_kwh = num("pellet energy content", M.PELLET_KWH_KG, "kWh/kg", step=0.1)
        cap_hp = num("heat pump thermal capacity (nominal)", M.CAP_HP_NOM, "W", step=500.0)
        cop0 = num("heat pump COP at 0 °C outdoor", 3.0, "", step=0.1)
        cop_slope = num("COP change per K outdoor", 0.07, "/K", step=0.01, format="%.2f")
        cop_min = num("COP floor", 1.8, "", step=0.1)
        cop_max = num("COP ceiling", 4.6, "", step=0.1)
        dhw_kwh = num("hot water when present", M.DHW_KWH_DAY, "kWh/day", step=0.5)
        base_occ = num("base electric load when present", 300.0, "W", step=50.0)
        base_abs = num("base electric load when away", 20.0, "W", step=5.0)
    with st.expander("PV & battery"):
        mod_wp = num("PV module power", 425.0, "Wp", step=25.0)
        mod_n = num("modules per roof pan", 15, "", step=1.0)
        pv_pr = num("PV performance ratio", M.PV_PR, "", step=0.05, format="%.2f")
        batt_kwh = num("battery capacity", 10.0, "kWh", step=1.0)
        batt_kw = num("battery charge/discharge power", 3.0, "kW", step=0.5)
        batt_eff = num("battery round-trip efficiency", 0.92, "", step=0.01, format="%.2f")
    with st.expander("Prices, investment & lifetimes"):
        p_elec = num("electricity price", M.ELEC_PRICE, "CHF/kWh", step=0.01, format="%.2f")
        p_feed = num("feed-in tariff", M.FEED_IN, "CHF/kWh", step=0.01, format="%.2f")
        p_stere = num("wood price", M.WOOD_PRICE_STERE, "CHF/stere", step=10.0)
        kwh_stere = num("wood energy content", M.WOOD_KWH_STERE, "kWh/stere", step=50.0)
        p_pel = num("pellet price", M.PELLET_PRICE_KG, "CHF/kg", step=0.02, format="%.2f")
        pel_capex = num("pellet stove installed cost", 7000.0, "CHF", step=500.0)
        pel_life = num("pellet stove lifetime", 15, "years", step=1.0, min_value=1.0)
        pv_capex = num("PV installed cost", 1800.0, "CHF/kWp", step=100.0)
        pv_life = num("PV lifetime", 30, "years", step=1.0, min_value=1.0)
        batt_capex = num("battery installed cost", 800.0, "CHF/kWh", step=50.0)
        batt_life = num("battery lifetime", 15, "years", step=1.0, min_value=1.0)
        hp_capex = num("heat pump installed cost", 12000.0, "CHF", step=500.0)
        hp_life = num("heat pump lifetime", 18, "years", step=1.0, min_value=1.0)

    with st.expander("CO₂ — operational factors"):
        elec_src = st.selectbox("electricity source", list(CB.ELEC_G_KWH),
                                index=list(CB.ELEC_G_KWH).index(CB.ELEC_DEFAULT),
                                help="Valais sells local hydro by default, but the "
                                     "marginal winter kWh is imported and much dirtier.")
        co2_elec = num("electricity", CB.ELEC_G_KWH[elec_src], "g CO₂eq/kWh", step=1.0,
                       key=f"in_co2_elec_{elec_src}")   # re-seeds when the source changes
        co2_pel = num("pellets (supply chain)", CB.PELLET_G_KWH, "g CO₂eq/kWh", step=1.0)
        co2_log = num("firewood logs (supply chain)", CB.WOOD_LOG_G_KWH,
                      "g CO₂eq/kWh", step=1.0)
        bio_pct = st.slider("biogenic CO₂ of wood counted as emitted (%)", 0, 100, 0,
                            step=5,
                            help="0 % = the forest regrows (standard Swiss "
                                 "accounting). Raise it if you doubt the wood is "
                                 "replanted: the chimney really emits "
                                 f"{CB.BIOGENIC_G_KWH:.0f} g/kWh.")
        ASSUM.append(("biogenic CO₂ counted", bio_pct, "%"))
        co2_bio = num("wood biogenic CO₂ at the chimney", CB.BIOGENIC_G_KWH,
                      "g CO₂eq/kWh", step=10.0)
    with st.expander("CO₂ — embodied in equipment"):
        pv_kg_kwp = num("PV embodied", CB.PV_KG_PER_KWP, "kg CO₂eq/kWp", step=50.0)
        batt_kg_kwh = num("battery embodied (LFP)", CB.BATT_KG_PER_KWH,
                          "kg CO₂eq/kWh", step=5.0)
        batt_cycles = num("battery cycle life", CB.BATT_CYCLE_LIFE, "full cycles",
                          step=500.0)
        hp_kg = num("heat pump embodied", CB.HP_KG, "kg CO₂eq", step=100.0)
        refrig_kg = num("refrigerant charge", CB.HP_REFRIG_KG, "kg", step=0.1,
                        format="%.1f")
        refrig_gwp = num("refrigerant GWP100", CB.HP_REFRIG_GWP, "", step=1.0,
                         help="R290 propane = 3, R32 = 675, R410A = 2088")
        refrig_leak = num("refrigerant leak rate", CB.HP_LEAK_YR * 100, "%/yr", step=0.5)
        pelstove_kg = num("pellet stove embodied", CB.PELLET_STOVE_KG, "kg CO₂eq",
                          step=50.0)
        horizon_y = num("impact horizon", CB.HORIZON_Y, "years", step=5.0,
                        min_value=5.0)

    if st.button("↩ reset everything to defaults", width="stretch"):
        st.session_state.clear()
        st.rerun()

# ------------------------------------------------------------------ derived quantities
a_win = aw + a_s
a_wall = (2 * (M.LEN_NS + M.LEN_EW) * M.EAVES_H
          + 2 * 0.5 * M.LEN_NS * (M.RIDGE_H - M.EAVES_H) - a_win)
h_trans = a_wall * u_wall + M.A_ROOF * u_roof + a_win * u_win + M.A_FLOOR * u_floor * M.B_FLOOR
h_tot = h_trans + ach * M.VOLUME * 0.34
c_eff = c_eff_kwh * 3.6e6
kwp_pan = mod_n * mod_wp / 1000.0
kwp_pv = {"none": 0.0, "half roof (south pan)": kwp_pan,
          "full roof (both pans)": 2 * kwp_pan}[pv_option]

w = weather(year)
occ = occupancy_array(*occ_spec)
occ_days = int(occ.sum() / 24)
poa = poa_surfaces()

SCEN_DEFS = {   # setpoint_abs, capacity (None = unlimited)
    "A — no heating (free-float)": (None, 0.0),
    "B — electric heaters": (sp_frost, cap_elec),
    "C — wood stove only": (None, cap_stove),
    "C2 — wood + electric frost guard": (sp_frost, cap_stove),
    "P — pellet stove (programmed: comfort + frost guard)": (sp_frost, cap_pel),
    "E — air-source heat pump": (sp_frost, None),
}

OFFGRID_MODE = {"B": "direct", "C2": "direct_away", "E": "hp", "P": "pellet"}

def scenario_at(name, yr):
    """(tin, q_heat, offgrid-series-or-None) for a scenario at climate year `yr`."""
    sp_abs, cap = SCEN_DEFS[name]
    key = name.split(" ")[0]
    if offgrid:
        return run_sim_offgrid(yr, occ_spec, sp_occ, sp_abs, cap,
                               OFFGRID_MODE.get(key, "none"), preheat, h_tot, c_eff,
                               aw, a_s, g_win, win_eff, q_occ, q_abs,
                               kwp_pv, kwp_pan, pv_pr, batt_kwh, batt_kw, batt_eff,
                               dhw_kwh, base_occ, base_abs,
                               cap_hp, cop0, cop_slope, cop_min, cop_max,
                               pel_el_run, pel_el_ign, pel_ign_min / 60.0)
    tin, qh = run_sim(yr, occ_spec, sp_occ, sp_abs, cap, preheat,
                      h_tot, c_eff, aw, a_s, g_win, win_eff, q_occ, q_abs)
    return tin, qh, None

def scenario_full(name):
    return scenario_at(name, year)

def scenario(name):
    tin, qh, _ = scenario_full(name)
    return tin, qh

# ------------------------------------------------------------------ header
st.title("Zinal chalet — interactive thermal model")
st.caption(f"Zinal, Val d'Anniviers (VS), ~1680 m · climate of **{year}** "
           "(CMIP6 day/night warming trends on the bias-corrected TMY) · "
           "x-axis shows a template year, times in UTC"
           + (" · **⚡ OFF-GRID: PV + battery only**" if offgrid else ""))
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("heat-loss coefficient", f"{h_tot:.0f} W/K")
k2.metric("time constant", f"{c_eff / h_tot / 3600:.0f} h")
k3.metric("days occupied", f"{occ_days}")
k4.metric("roof surface", f"{M.A_ROOF:.0f} m²")
k5.metric("PV selected", f"{kwp_pv:.1f} kWp")

with st.expander("🏠 House, terrain & sun paths (3D — drag to rotate)", expanded=True):
    st.plotly_chart(scene_fig(), width="stretch")
    st.caption("Sun paths for 21 Dec / 21 Mar / 21 Jun — strong line = sun visible, "
               "faint = behind the mountains; dots = full hours on the June and "
               "December paths. Grey wall = the real mountain horizon (PVGIS DEM); "
               "roof pans face south and north.")

if not enabled:
    st.info("Enable at least one scenario in the sidebar to see indoor temperatures.")

# ------------------------------------------------------------------ hourly plot
st.subheader(f"Hour-by-hour temperature — climate {year}")
st.caption("Blue shading = periods when you are at the chalet.")
hours = pd.date_range("2026-01-01", periods=8760, freq="h")
days = pd.date_range("2026-01-01", periods=365, freq="D")

fig1 = go.Figure()
# shade the occupied periods
occ_d = occ.reshape(365, 24).any(axis=1)
edges = np.flatnonzero(np.diff(np.r_[False, occ_d, False]))
for s, e in zip(edges[::2], edges[1::2]):
    fig1.add_vrect(x0=days[s], x1=days[e - 1] + pd.Timedelta(days=1),
                   fillcolor=rgba("#2a78d6", 0.07), line_width=0, layer="below")
fig1.add_trace(go.Scattergl(x=hours, y=w["t2m"], name="outside",
                            line=dict(color=OUTSIDE_C, width=1)))
for name in enabled:
    tin, _ = scenario(name)
    fig1.add_trace(go.Scattergl(x=hours, y=tin, name=name,
                                line=dict(color=SCEN_COLORS[name], width=1.1)))
fig1.update_layout(height=470, margin=dict(l=10, r=10, t=30, b=10),
                   yaxis_title="temperature (°C)", hovermode="x",
                   legend=dict(orientation="h", yanchor="bottom", y=1.01))
st.plotly_chart(fig1, width="stretch")

# ------------------------------------------------------------------ daily plot
st.subheader("Daily view — mean and ±1σ / 2σ / 3σ of each day's 24 hourly values")

def daily(arr):
    a = np.asarray(arr).reshape(365, 24)
    return a.mean(axis=1), a.std(axis=1)

fig2 = go.Figure()
series = [("outside", w["t2m"], OUTSIDE_C)] + \
         [(n, scenario(n)[0], SCEN_COLORS[n]) for n in enabled]
for name, arr, col in series:
    mu, sd = daily(arr)
    for k, alpha in ((3, 0.06), (2, 0.10), (1, 0.16)):
        fig2.add_trace(go.Scatter(
            x=days.append(days[::-1]), y=np.r_[mu + k * sd, (mu - k * sd)[::-1]],
            fill="toself", fillcolor=rgba(col, alpha), line=dict(width=0),
            hoverinfo="skip", legendgroup=name, showlegend=False))
    fig2.add_trace(go.Scatter(x=days, y=mu, name=name, legendgroup=name,
                              line=dict(color=col, width=2)))
fig2.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=10),
                   yaxis_title="temperature (°C)", hovermode="x",
                   legend=dict(orientation="h", yanchor="bottom", y=1.01))
st.plotly_chart(fig2, width="stretch")
st.caption("Click a legend entry to hide a series together with its bands.")

# ------------------------------------------------------------------ loads & helpers
dhw_e = dhw_kwh * occ_days                              # kWh/yr electric DHW
dhw_w = np.zeros(8760)
dhw_w[occ & (tmy()["hour"] >= 11) & (tmy()["hour"] < 17)] = dhw_kwh * 1000.0 / 6.0
base_w = np.where(occ, base_occ, base_abs)              # plugs: present vs standby
kwh = lambda q: float(np.sum(q)) / 1000.0
base_kwh = kwh(base_w)

def hp_electric(need, ww=None):
    """Hourly heat-pump electricity (W) incl. resistance backup above capacity."""
    t2m = (ww or w)["t2m"]
    cap_w = cap_hp * np.clip(1 + 0.025 * np.minimum(t2m + 7, 0), 0.55, 1.0)
    q_hp = np.minimum(need, cap_w)
    cop = np.clip(cop0 + cop_slope * t2m, cop_min, cop_max)
    return q_hp / cop + (need - q_hp)

def fuel_and_power(name, yr):
    """(electricity kWh, pellets kg, wood steres) bought in one year at climate `yr`."""
    _, q_heat, ser = scenario_at(name, yr)
    key = name.split(" ")[0]
    if offgrid:                       # nothing is bought from a grid that isn't there
        e = 0.0
    elif key == "A":
        e = dhw_e + base_kwh
    elif key == "B":
        e = kwh(q_heat) + dhw_e + base_kwh
    elif key == "C2":
        e = kwh(q_heat[~occ]) + dhw_e + base_kwh
    elif key == "C":
        e = dhw_e + base_kwh
    elif key == "P":
        e = kwh(pellet_aux(q_heat)) + dhw_e + base_kwh
    else:                             # E, heat pump
        e = kwh(hp_electric(q_heat, weather(yr))) + dhw_e + base_kwh
    kg = kwh(q_heat) / (pel_eff * pel_kwh) if key == "P" else 0.0
    st_ = (kwh(q_heat[occ]) if key == "C2" else kwh(q_heat)) / (stove_eff * kwh_stere) \
        if key.startswith("C") else 0.0
    return e, kg, st_

def operational_parts(name, yr):
    """kg CO₂eq for one year at climate `yr`, split by source."""
    e, kg, st_ = fuel_and_power(name, yr)
    fuel_pel, fuel_log = kg * pel_kwh, st_ * kwh_stere      # kWh of fuel burnt
    return {"grid electricity": e * co2_elec / 1000.0,
            "pellets (supply chain)": fuel_pel * co2_pel / 1000.0,
            "firewood (supply chain)": fuel_log * co2_log / 1000.0,
            "wood CO₂ not regrown": (fuel_pel + fuel_log) * co2_bio
                                    * (bio_pct / 100.0) / 1000.0}

def operational_co2(name, yr):
    """kg CO₂eq bought-energy emissions for one year at climate `yr`."""
    return sum(operational_parts(name, yr).values())

def pellet_aux(q_heat):
    """Hourly electricity (W) of the pellet stove's electronics: running draw while
    it burns + an ignition surge on each hour that (re)lights the burner."""
    on = q_heat > 0
    start = on & ~np.roll(on, 1)
    start[0] = on[0]
    return on * pel_el_run + start * (pel_el_ign - pel_el_run) * (pel_ign_min / 60.0)

def pv_array():
    if kwp_pv == 0:
        return np.zeros(8760)
    if kwp_pv <= kwp_pan:
        return kwp_pv * poa["roof_s"] * pv_pr
    return kwp_pan * (poa["roof_s"] + poa["roof_n"]) * pv_pr

# ------------------------------------------------------------------ electricity flows
st.subheader("Electricity flows — solar, battery, grid, usage")
if enabled:
    e_names = [n for n in enabled if n.startswith("E")]
    flow_basis = st.selectbox("heating system for the electricity balance", enabled,
                              index=enabled.index(e_names[0]) if e_names else 0,
                              help="PV + battery are dispatched against this "
                                   "scenario's hourly electric load.")
    tin_f, q_heat_f, ser_og = scenario_full(flow_basis)
    pv_flow = pv_array()
    if offgrid:
        ser = ser_og
        heat_el = ser["heat_el"]                          # served heating electricity
        heat_el_dem = heat_el + ser["unserved_heat_el"]   # what heating asked for
        f_imp, f_exp = 0.0, 0.0
        curt = kwh(ser["curtailed"])
        unserved_kwh = kwh(ser["unserved_aux"]) + kwh(ser["unserved_heat_el"])
    else:
        if flow_basis.startswith("B"):
            heat_el = q_heat_f
        elif flow_basis.startswith("C2"):
            heat_el = np.where(occ, 0.0, q_heat_f)   # stove when there, electric guard away
        elif flow_basis.startswith("E"):
            heat_el = hp_electric(q_heat_f)
        elif flow_basis.startswith("P"):
            heat_el = pellet_aux(q_heat_f)           # stove electronics only
        else:
            heat_el = np.zeros(8760)                 # wood heat: no heating electricity
        heat_el_dem = heat_el
        load_flow = heat_el + dhw_w + base_w
        f_imp, f_exp, f_selfc, ser = battery_series(pv_flow, load_flow,
                                                    batt_kwh, batt_kw * 1000, batt_eff)
        curt, unserved_kwh = 0.0, 0.0
    pv_tot = kwh(pv_flow)
    load_tot = kwh(heat_el_dem + dhw_w + base_w)
    pvd = kwh(ser["pv_direct"])
    chg = kwh(ser["batt_charge"])
    dis = kwh(ser["batt_discharge"])

    if offgrid and pv_tot == 0:
        st.warning("Off-grid with PV set to *none* — there is no electricity source "
                   "at all: no plugs, no hot water, and no electric heating.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("electricity demand", f"{load_tot:,.0f} kWh/yr")
    if offgrid:
        m2.metric("unserved (blackout)", f"{unserved_kwh:,.0f} kWh/yr")
        m3.metric("PV curtailed", f"{curt / pv_tot * 100:.0f} %" if pv_tot else "—")
    else:
        m2.metric("self-sufficiency",
                  f"{(1 - f_imp / load_tot) * 100:.0f} %" if load_tot else "—")
        m3.metric("PV self-consumed",
                  f"{(1 - f_exp / pv_tot) * 100:.0f} %" if pv_tot else "—")
    m4.metric("battery cycles",
              f"{dis / batt_kwh:.0f} /yr" if batt_kwh and pv_tot else "—")

    # breakdowns shared by the Sankey and the daily panels
    standby_w = np.full(8760, float(base_abs))           # always-on floor
    occ_use_w = (base_w - base_abs) + dhw_w              # extra plugs when there + DHW
    q_sol_flow = (aw * poa["win_w"] + a_s * poa["win_s"]) * g_win * win_eff
    q_int_w = np.where(occ, q_occ, q_abs)                # people, cooking, appliances
    # heat not carried by electricity (pellet aux power is not heat: it runs fans/auger)
    if flow_basis.startswith("P"):
        rest_w, heat_el_is_heat = q_heat_f, np.zeros(8760)
    else:
        rest_w, heat_el_is_heat = q_heat_f - heat_el, heat_el
    rest_lab, rest_col = (("outside air via heat pump", "#1baf7a")
                          if flow_basis.startswith("E") else
                          ("pellets", "#b08d63") if flow_basis.startswith("P") else
                          ("wood stove", "#b08d63") if flow_basis.startswith("C")
                          else (None, None))
    standby_kwh, occu_kwh = kwh(standby_w), kwh(occ_use_w)
    heat_el_kwh, rest_kwh = kwh(heat_el_is_heat), kwh(rest_w)
    qint_kwh, qsol_kwh = kwh(q_int_w), kwh(q_sol_flow)
    house_heat = heat_el_kwh + rest_kwh + qint_kwh + qsol_kwh

    # annual Sankey: electricity broken down by end use + where the heat comes from
    nodes = []
    def node(label, color):
        nodes.append((label, color))
        return len(nodes) - 1
    links = []
    served_el = pvd + dis + f_imp
    if offgrid:
        aux_served = max(standby_kwh + occu_kwh - kwh(ser["unserved_aux"]), 0.0)
        sh = standby_kwh / max(standby_kwh + occu_kwh, 1e-9)
        stb_v, occ_v = aux_served * sh, aux_served * (1 - sh)
    else:
        stb_v, occ_v = standby_kwh, occu_kwh
    EL = node(f"electricity {served_el:,.0f} kWh", "#2a78d6")
    if pv_tot > 0:
        PV = node(f"PV {pv_tot:,.0f} kWh", "#eda100")
        BAT = node("battery", "#1baf7a")
        spill = curt if offgrid else f_exp
        EXP = node(("curtailed " if offgrid else "export ") + f"{spill:,.0f} kWh",
                   "#eb6834")
        BLOSS = node("battery losses", "#898781")
        links += [(PV, EL, pvd), (PV, BAT, chg), (PV, EXP, spill),
                  (BAT, EL, dis), (BAT, BLOSS, max(chg - dis, 0.0))]
    if f_imp > 0.5:
        GR = node(f"grid {f_imp:,.0f} kWh", "#8a63d2")
        links.append((GR, EL, f_imp))
    STB = node(f"standby {stb_v:,.0f} kWh", "#898781")
    OCC = node(f"occupation: plugs + hot water {occ_v:,.0f} kWh", "#2a78d6")
    HH = node(f"house heat {house_heat:,.0f} kWh", "#d6567d")
    links += [(EL, STB, stb_v), (EL, OCC, occ_v), (EL, HH, heat_el_kwh)]
    if rest_kwh > 0.5 and rest_lab:
        if flow_basis.startswith("E"):
            AIR = node(f"outside air {rest_kwh:,.0f} kWh", "#1baf7a")
            links.append((AIR, HH, rest_kwh))
        else:
            f_eff = pel_eff if flow_basis.startswith("P") else stove_eff
            fuel_in = rest_kwh / f_eff
            FUE = node(f"{rest_lab} {fuel_in:,.0f} kWh", "#b08d63")
            FLO = node("flue losses", "#898781")
            links += [(FUE, HH, rest_kwh), (FUE, FLO, fuel_in - rest_kwh)]
    PEO = node(f"occupants & appliances {qint_kwh:,.0f} kWh", "#d6567d")
    SUN = node(f"sun through windows {qsol_kwh:,.0f} kWh", "#eda100")
    links += [(PEO, HH, qint_kwh), (SUN, HH, qsol_kwh)]
    links = [l for l in links if l[2] > 0.5]
    fig_s = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[n[0] for n in nodes], color=[n[1] for n in nodes],
                  pad=18, thickness=16),
        link=dict(source=[l[0] for l in links], target=[l[1] for l in links],
                  value=[round(l[2]) for l in links],
                  color=[rgba(nodes[l[0]][1], 0.30) for l in links])))
    fig_s.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_s, width="stretch")
    st.caption("Annual flows in kWh. Left: where electricity comes from; middle: what "
               "it is used for (standby / occupation / heating); right: everything "
               "that heats the rooms, including the free contributions (outside air "
               "via the heat pump's COP, occupants, sun). Hot water is counted as "
               "occupation usage, not house heat — it leaves down the drain.")

    fig3 = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                         subplot_titles=("electricity usage by end use (kWh/day)",
                                         "electricity by source — export below zero (kWh/day)",
                                         "thermal energy into the house by origin (kWh/day)"))
    dsum = lambda a: np.asarray(a).reshape(365, 24).sum(axis=1) / 1000.0
    for name_t, arr, col in [("standby (always on)", standby_w, "#898781"),
                             ("occupation usage (plugs + hot water)", occ_use_w, "#2a78d6"),
                             ("heating related", heat_el_dem, "#eb6834")]:
        fig3.add_trace(go.Scatter(x=days, y=dsum(arr), name=name_t, stackgroup="use",
                                  mode="none", fillcolor=rgba(col, 0.75)), row=1, col=1)
    src = [("PV used directly", ser["pv_direct"], "#eda100"),
           ("from battery", ser["batt_discharge"], "#1baf7a")]
    if offgrid:
        src.append(("unserved (blackout)",
                    ser["unserved_aux"] + ser["unserved_heat_el"], "#d6567d"))
    else:
        src.append(("from grid", ser["grid_import"], "#8a63d2"))
    for name_t, arr, col in src:
        fig3.add_trace(go.Scatter(x=days, y=dsum(arr), name=name_t, stackgroup="src",
                                  mode="none", fillcolor=rgba(col, 0.75)), row=2, col=1)
    if pv_tot > 0:
        spill_arr = ser["curtailed"] if offgrid else ser["grid_export"]
        fig3.add_trace(go.Scatter(
            x=days, y=-dsum(spill_arr), mode="none", fill="tozeroy",
            name="curtailed PV (no grid)" if offgrid else "export (PV surplus)",
            fillcolor=rgba("#eda100", 0.35)), row=2, col=1)

    # thermal energy delivered to the house, by origin
    therm = []
    if rest_lab and rest_w.sum() > 0:
        therm.append((f"heating: {rest_lab}", rest_w, rest_col))
    if heat_el_is_heat.sum() > 0:
        therm.append(("heating: electricity → heat", heat_el_is_heat, "#8a63d2"))
    therm += [("people & appliances (internal gains)", q_int_w, "#d6567d"),
              ("sun through the windows", q_sol_flow, "#eda100")]
    for name_t, arr, col in therm:
        fig3.add_trace(go.Scatter(x=days, y=dsum(arr), name=name_t, stackgroup="heat",
                                  mode="none", fillcolor=rgba(col, 0.75)), row=3, col=1)

    fig3.update_layout(height=820, margin=dict(l=10, r=10, t=30, b=10), hovermode="x",
                       legend=dict(orientation="h", yanchor="bottom", y=1.03))
    st.plotly_chart(fig3, width="stretch")
    st.caption(f"End-use split: **standby** = the {base_abs:.0f} W that runs all year "
               f"(fridge, router); **occupation usage** = the extra "
               f"{base_occ - base_abs:.0f} W of plugs while someone is there plus "
               f"{dhw_kwh:.0f} kWh/day of hot water on occupied days; **heating "
               f"related** = the heating electricity of the selected scenario "
               f"(all editable under *Heating systems*). PV: {pv_option}. "
               "The thermal panel shows all heat entering the rooms: with the heat "
               "pump, only ~1/COP of the heat is electricity — the rest is pumped "
               "for free out of the outside air; sun and occupants heat the house "
               "in every scenario.")

# ------------------------------------------------------------------ energy & cost table
st.subheader(f"Energy & yearly cost — climate {year}, {occ_days} days occupied")

rows = []
def add_row(name, heat, elec, wood, run_cost, capex, tin, pellets=0.0):
    rows.append({"scenario": name, "heat delivered kWh": round(heat),
                 "electricity kWh": round(elec), "wood steres": round(wood, 1),
                 "pellets kg": round(pellets),
                 "running CHF/yr": round(run_cost), "investment CHF/yr": round(capex),
                 "TOTAL CHF/yr": round(run_cost + capex),
                 "min indoor °C": round(float(tin.min()), 1),
                 "h < 0 °C indoor": int((tin < 0).sum())})

grid_p = 0.0 if offgrid else p_elec          # off-grid: nothing is bought from the grid
need_e = None
for name in enabled:
    tin, q_heat = scenario(name)
    if name.startswith("A"):
        e0 = dhw_e + base_kwh
        add_row(name, 0, e0, 0, e0 * grid_p, 0, tin)
    elif name.startswith("B"):
        e = kwh(q_heat) + dhw_e + base_kwh
        add_row(name, kwh(q_heat), e, 0, e * grid_p, 0, tin)
    elif name.startswith("C2"):
        q_o, q_a = kwh(q_heat[occ]), kwh(q_heat[~occ])
        steres = q_o / (stove_eff * kwh_stere)
        add_row(name, q_o + q_a, q_a + dhw_e + base_kwh, steres,
                steres * p_stere + (q_a + dhw_e + base_kwh) * grid_p, 0, tin)
    elif name.startswith("C"):
        steres = kwh(q_heat) / (stove_eff * kwh_stere)
        add_row(name, kwh(q_heat), dhw_e + base_kwh, steres,
                steres * p_stere + (dhw_e + base_kwh) * grid_p, 0, tin)
    elif name.startswith("P"):
        kg = kwh(q_heat) / (pel_eff * pel_kwh)   # thermostat + timer: covers everything
        e_aux = kwh(pellet_aux(q_heat))          # fans, auger, igniter
        add_row(name, kwh(q_heat), e_aux + dhw_e + base_kwh, 0,
                kg * p_pel + (e_aux + dhw_e + base_kwh) * grid_p,
                pel_capex / pel_life, tin, pellets=kg)
    elif name.startswith("E"):
        need_e = (tin, q_heat)

if need_e is None and kwp_pv > 0 and not offgrid:   # PV row needs the heat-pump load
    need_e = scenario("E — air-source heat pump")

if need_e is not None:
    tin, need = need_e
    elec_hp_w = hp_electric(need)
    e_hp = kwh(elec_hp_w) + dhw_e + base_kwh
    hp_cap_yr = hp_capex / hp_life
    if "E — air-source heat pump" in enabled:
        add_row("E — air-source heat pump", kwh(need), e_hp,
                0, e_hp * grid_p, hp_cap_yr, tin)
    if kwp_pv > 0 and not offgrid:
        pv_w_arr = pv_array()
        load_w = elec_hp_w + dhw_w + base_w
        imp, exp, selfc, _ = battery_series(pv_w_arr, load_w,
                                            batt_kwh, batt_kw * 1000, batt_eff)
        capex = hp_cap_yr + kwp_pv * pv_capex / pv_life + batt_kwh * batt_capex / batt_life
        add_row(f"E + PV {pv_option} ({kwp_pv:.1f} kWp) + battery",
                kwh(need), imp, 0, imp * p_elec - exp * p_feed, capex, tin)
        st.caption(f"PV production {kwh(pv_w_arr):,.0f} kWh/yr "
                   f"({kwh(pv_w_arr) / 365:.1f} kWh/day avg) — self-consumed "
                   f"{selfc:,.0f} kWh, exported {exp:,.0f} kWh, imported {imp:,.0f} kWh.")

if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if offgrid:
        og_capex = kwp_pv * pv_capex / pv_life + batt_kwh * batt_capex / batt_life
        st.caption(f"**Off-grid**: no grid purchases or feed-in — electricity comes "
                   f"from PV + battery only (their investment, "
                   f"{og_capex:,.0f} CHF/yr amortized, applies to the whole house "
                   f"on top of each row). Electric heating that cannot be powered "
                   f"is simply not delivered — see the *min indoor* and *h < 0 °C* "
                   f"columns, and the unserved kWh in the flow section above.")
    st.caption(f"Every row includes hot water ({dhw_e:.0f} kWh) and plug/standby "
               f"electricity ({base_kwh:.0f} kWh: {base_occ:.0f} W present / "
               f"{base_abs:.0f} W away). Investment = installed cost / lifetime "
               "(straight-line, no interest); electric heaters and the existing wood "
               "stove count as zero investment, the pellet stove and heat pump are "
               "amortized. PV changes costs only — indoor temperature follows the "
               "heat-pump scenario.")

# ------------------------------------------------------------------ CO2
st.subheader(f"CO₂ footprint — yearly use and {horizon_y:.0f}-year total")

if enabled:
    pv_life_co2 = pv_life                      # same lifetimes as the cost side
    cyc = dis / batt_kwh if batt_kwh else 0.0  # battery cycles/yr from the flow section
    batt_life_eff = CB.battery_life(cyc, cal_life=batt_life, cycle_life=batt_cycles)
    pv_items = [("PV manufacture", kwp_pv * pv_kg_kwp, pv_life_co2),
                ("battery manufacture", batt_kwh * batt_kg_kwh, batt_life_eff)]
    hp_refrig = CB.refrigerant_kg(refrig_kg, refrig_gwp, refrig_leak / 100.0,
                                  CB.HP_LEAK_EOL, hp_life, horizon_y)

    def pv_grid_import(yr):
        """Grid kWh of the heat-pump + PV + battery combination at climate `yr`."""
        _, need, _ = scenario_at("E — air-source heat pump", yr)
        load = hp_electric(need, weather(yr)) + dhw_w + base_w
        return battery_series(pv_array(), load, batt_kwh, batt_kw * 1000, batt_eff)[0]

    def build(label, parts_now, parts_end, items, extra=None):
        """Blend one year's operational parts over the horizon and add equipment.

        Returns (label, components kg over the horizon, this year's operational kg).
        """
        comp = {k: horizon_y * (parts_now[k] + parts_end[k]) / 2.0 for k in parts_now}
        for it_name, kg, life in items:
            comp[it_name] = (comp.get(it_name, 0.0)
                             + CB.units_needed(life, horizon_y) * kg)
        if extra:
            comp.update(extra)
        return label, comp, sum(parts_now.values())

    specs = []
    for name in enabled:
        key = name.split(" ")[0]
        items, extra = [], None
        if key == "P":
            items.append(("pellet stove manufacture", pelstove_kg, pel_life))
        if key == "E":
            items.append(("heat pump manufacture", hp_kg, hp_life))
            extra = {"refrigerant leakage": hp_refrig}
        if offgrid and kwp_pv > 0:      # off-grid: PV+battery power the whole house
            items += pv_items
        specs.append(build(name, operational_parts(name, year),
                           operational_parts(name, year + horizon_y), items, extra))
    if need_e is not None and kwp_pv > 0 and not offgrid:
        zero = {k: 0.0 for k in ("pellets (supply chain)", "firewood (supply chain)",
                                 "wood CO₂ not regrown")}
        specs.append(build(
            f"E + PV {pv_option} + battery",
            dict(zero, **{"grid electricity": pv_grid_import(year) * co2_elec / 1000}),
            dict(zero, **{"grid electricity":
                          pv_grid_import(year + horizon_y) * co2_elec / 1000}),
            [("heat pump manufacture", hp_kg, hp_life)] + pv_items,
            {"refrigerant leakage": hp_refrig}))

    SRC_COLORS = {"grid electricity": "#8a63d2",
                  "pellets (supply chain)": "#b08d63",
                  "firewood (supply chain)": "#6f5a3e",
                  "wood CO₂ not regrown": "#eb6834",
                  "PV manufacture": "#eda100",
                  "battery manufacture": "#1baf7a",
                  "heat pump manufacture": "#2a78d6",
                  "refrigerant leakage": "#d6567d",
                  "pellet stove manufacture": "#898781"}
    used = [s for s in SRC_COLORS if any(sp[1].get(s, 0) > 0.5 for sp in specs)]

    co2_rows = []
    for label, comp, op_now in specs:
        row = {"scenario": label, "kg CO₂/yr now": round(op_now)}
        row.update({f"{s} (t)": round(comp.get(s, 0.0) / 1000, 2) for s in used})
        row[f"TOTAL t CO₂ ({horizon_y:.0f} y)"] = round(sum(comp.values()) / 1000, 1)
        co2_rows.append(row)
    st.dataframe(pd.DataFrame(co2_rows), width="stretch", hide_index=True)

    fig_c = go.Figure()
    short = [lbl.split(" — ")[0] + " " + lbl.split(" — ")[-1][:24] for lbl, _, _ in specs]
    for s in used:
        fig_c.add_trace(go.Bar(y=short, x=[sp[1].get(s, 0.0) / 1000 for sp in specs],
                               name=s, orientation="h", marker_color=SRC_COLORS[s]))
    fig_c.update_layout(barmode="stack", height=120 + 46 * len(specs),
                        margin=dict(l=10, r=10, t=30, b=10),
                        xaxis_title=f"tonnes CO₂eq over {horizon_y:.0f} years",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig_c, width="stretch")

    st.caption(
        f"**Electricity** at {co2_elec:.0f} g CO₂eq/kWh ({elec_src}) — the Valais "
        "product is local hydro, but a January kWh is really imported: switch the "
        "source in the sidebar to see how much that matters. "
        f"**Pellets** at {co2_pel:.0f} g/kWh of fuel (proPellets.ch / KBOB: "
        "harvesting, drying, pelletizing, transport), with the chimney's biogenic "
        f"CO₂ counted at **{bio_pct} %** — at 0 % you assume the forest fully "
        f"regrows; the stack itself emits {co2_bio:.0f} g/kWh. "
        f"**Equipment** is amortized by rebuying it whenever it wears out inside the "
        f"{horizon_y:.0f} years: PV every {pv_life_co2:.0f} y, battery every "
        f"{batt_life_eff:.0f} y (LFP at {cyc:.0f} cycles/yr → "
        + ("calendar-limited" if batt_life_eff >= batt_life - 1e-6 else "cycle-limited")
        + f"), heat pump every {hp_life:.0f} y (+ refrigerant GWP {refrig_gwp:.0f} "
        f"leaking {refrig_leak:.1f} %/yr), pellet stove every {pel_life:.0f} y. "
        "Use-phase emissions are averaged between today's and the "
        f"{year + horizon_y:.0f} climate, so the declining heating demand is included.")

# ------------------------------------------------------------------ assumptions echo
with st.expander("📋 All assumptions & derived values (current)"):
    fixed = [
        ("footprint", f"{M.LEN_NS:.0f} × {M.LEN_EW:.0f}", "m"),
        ("eaves / ridge height", f"{M.EAVES_H:.1f} / {M.RIDGE_H:.2f}", "m"),
        ("roof pitch (ridge E-W, pans S/N)", f"{np.degrees(M.ROOF_PITCH):.1f}", "°"),
        ("roof surface (total / per pan)", f"{M.A_ROOF:.1f} / {M.A_ROOF_PAN:.1f}", "m²"),
        ("wall area (net of windows)", f"{a_wall:.1f}", "m²"),
        ("heated floor area / volume", f"{M.FLOOR_AREA:.0f} / {M.VOLUME:.0f}", "m² / m³"),
        ("heat-loss coefficient H (derived)", f"{h_tot:.1f}", "W/K"),
        ("time constant (derived)", f"{c_eff / h_tot / 3600:.1f}", "h"),
        ("PV per pan (derived)", f"{kwp_pan:.2f}", "kWp"),
        ("floor temp. reduction factor b", f"{M.B_FLOOR}", ""),
        ("ground albedo Nov–Apr / May–Oct", "0.6 / 0.2", ""),
        ("HP capacity derating", "−2.5 %/K below −7 °C, floor 55 %", ""),
        ("climate trend (fit 2026-2050, extrapolated)",
         f"day +{np.mean(warming_slopes()['day']) * 10:.2f}, "
         f"night +{np.mean(warming_slopes()['night']) * 10:.2f}", "K/decade"),
    ]
    df = pd.DataFrame([{"assumption": n,
                        "value": f"{v:g}" if isinstance(v, (int, float)) else str(v),
                        "unit": u, "editable": e}
                       for n, v, u, e in
                       [(n, v, u, "yes") for n, v, u in ASSUM] +
                       [(n, v, u, "no (edit model.py)") for n, v, u in fixed]])
    st.dataframe(df, width="stretch", hide_index=True, height=520)
