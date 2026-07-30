"""
Scenario simulation for the Zinal chalet (see model.py for the physics & data).

Scenarios
  A  do nothing          : free-floating temperature, no heating at all
  B  electric heaters    : 20 C occupied, 7 C frost-guard when absent
  C  wood stove          : stove when occupied only (no heat when absent)
  C2 wood + frost guard  : stove occupied + electric 7 C when absent
  D  + solar thermal     : 4 m2 collector, DHW + space support on top of B
  E  air-source heat pump: same setpoints as B, COP(T) model
  F  PV half roof        : south pan filled (6.4 kWp) + 10 kWh battery feeding E
  F2 PV full roof        : both pans (12.8 kWp) + 10 kWh battery feeding E

Occupancy: typical secondary-home calendar (~70 days/yr), configurable below.
Climate: every run is shifted to a target year with day/night-specific monthly
warming trends (CMIP6-HighRes); horizons now / +10 / +20 / +30 / +40 / +50 years.
"""
import numpy as np
import os
import model as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---------------------------------------------------------------- occupancy calendar
def occupancy(w):
    """Boolean hourly array. Holidays + every-other-weekend, ~70 days/yr."""
    doy = w["doy"].astype(int)
    occ = np.zeros(len(doy), bool)
    holidays = set()
    holidays.update(range(358, 366)); holidays.update(range(1, 5))    # Dec 24 - Jan 4
    holidays.update(range(39, 47))                                    # Feb week
    holidays.update(range(196, 218))                                  # Jul 15 - Aug 5
    weekday = (doy - 1) % 7          # doy 1 = "Monday"
    week = (doy - 1) // 7
    weekend_months = np.isin(w["month"], (1, 2, 3, 4, 9, 10, 12))
    wknd = (week % 2 == 0) & np.isin(weekday, (5, 6)) & weekend_months
    occ = np.isin(doy, list(holidays)) | wknd
    return occ

# ---------------------------------------------------------------- helpers
def kwh(q_w):
    return float(np.sum(q_w)) / 1000.0

def freeze_stats(tin):
    return dict(t_min=float(tin.min()),
                h_below0=int(np.sum(tin < 0)),
                h_below5=int(np.sum(tin < 5)),
                t_max=float(tin.max()),
                h_above26=int(np.sum(tin > 26)))

def pv_production(w, el, az, hz, svf, kwp, tilt, surf_az):
    """Hourly AC output (W) for kwp installed at tilt/azimuth."""
    alb = M.snow_albedo(w["month"])
    poa = M.poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"],
                           tilt, surf_az, hz, svf, alb)
    return kwp * 1000.0 * poa / 1000.0 * M.PV_PR

def battery_dispatch(pv_w, load_w, cap_kwh=10.0, p_max=3000.0, eff=0.92,
                     return_series=False):
    """Greedy self-consumption. Returns (grid_import_kWh, export_kWh, self_cons_kWh);
    with return_series=True additionally a dict of hourly arrays (W):
    pv_direct, batt_charge (AC in), batt_discharge (AC out), grid_import,
    grid_export, soc (Wh stored)."""
    soc = 0.0
    cap = cap_kwh * 1000.0  # Wh
    imp = exp = self_c = 0.0
    sq = np.sqrt(eff)
    ser = ({k: np.zeros(len(pv_w)) for k in
            ("pv_direct", "batt_charge", "batt_discharge",
             "grid_import", "grid_export", "soc")} if return_series else None)
    for i, (pv, ld) in enumerate(zip(pv_w, load_w)):
        direct = min(pv, ld)
        self_c += direct
        surplus, deficit = pv - direct, ld - direct
        chg = dis_ac = ex = im = 0.0
        if surplus > 0:
            chg = min(surplus, p_max, (cap - soc) / sq)
            soc += chg * sq
            ex = surplus - chg
            exp += ex
        if deficit > 0:
            dis = min(deficit / sq, p_max, soc)
            soc -= dis
            dis_ac = dis * sq
            self_c += dis_ac
            im = deficit - dis_ac
            imp += im
        if ser is not None:
            ser["pv_direct"][i] = direct; ser["batt_charge"][i] = chg
            ser["batt_discharge"][i] = dis_ac; ser["grid_import"][i] = im
            ser["grid_export"][i] = ex; ser["soc"][i] = soc
    out = (imp / 1000.0, exp / 1000.0, self_c / 1000.0)
    return out + (ser,) if return_series else out

def dhw_load(w, occ):
    """Electric DHW: 3 kWh/day on occupied days, drawn 11h-17h UTC (allows PV)."""
    load = np.zeros(len(occ))
    day_hours = (w["hour"] >= 11) & (w["hour"] < 17)
    load[occ & day_hours] = 3000.0 / 6.0
    return load

def solar_thermal(w, el, az, hz, svf, area=4.0, tilt=60.0, surf_az=180.0):
    """Flat-plate collector gross output (W): eta = 0.75 - 3.5*(45-Ta)/G."""
    alb = M.snow_albedo(w["month"])
    poa = M.poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"],
                           tilt, surf_az, hz, svf, alb)
    with np.errstate(divide="ignore", invalid="ignore"):
        eta = 0.75 - 3.5 * (45.0 - w["t2m"]) / np.where(poa > 30, poa, np.inf)
    return area * poa * np.clip(eta, 0, 0.75)

# ---------------------------------------------------------------- main
def run(tag="TMY", year=None, slopes=None):
    w = M.load_tmy()
    if year is not None:                     # shift to target-year climate, day/night trends
        w = M.apply_warming(w, year, slopes)
    hz = M.load_horizon()
    svf = M.sky_view_factor(hz)
    q_sol, el, az = M.solar_gains(w, hz, svf)
    occ = occupancy(w)
    occ_days = int(np.sum(occ) / 24)
    base = np.where(occ, 300.0, 20.0)     # plugs/fridge/router when present, standby when not
    e_base = kwh(base)
    e_dhw = 3.0 * occ_days
    res = {}

    # --- A: do nothing (no heating; plugs + DHW still run when present)
    a = M.simulate(w, q_sol, occ, setpoint_abs=None, capacity=0.0)
    res["A do nothing"] = dict(freeze_stats(a["tin"]), heat_kwh=0,
                               elec_kwh=e_dhw + e_base,
                               cost=(e_dhw + e_base) * M.ELEC_PRICE)
    tin_free = a["tin"]

    # --- B: electric heaters, frost guard 7 C
    b = M.simulate(w, q_sol, occ, setpoint_abs=7.0, capacity=M.CAP_ELECTRIC)
    q_occ = kwh(b["q_heat"][occ]); q_abs = kwh(b["q_heat"][~occ])
    res["B electric"] = dict(freeze_stats(b["tin"]), heat_kwh=q_occ + q_abs,
                             heat_occ=q_occ, heat_frost=q_abs,
                             elec_kwh=q_occ + q_abs + e_dhw + e_base,
                             cost=(q_occ + q_abs + e_dhw + e_base) * M.ELEC_PRICE)

    # --- C: wood stove only when occupied
    c = M.simulate(w, q_sol, occ, setpoint_abs=None, capacity=M.CAP_STOVE)
    wood_del = kwh(c["q_heat"])
    steres = wood_del / (M.STOVE_EFF * M.WOOD_KWH_STERE)
    res["C wood only"] = dict(freeze_stats(c["tin"]), heat_kwh=wood_del,
                              steres=steres, elec_kwh=e_dhw + e_base,
                              cost=steres * M.WOOD_PRICE_STERE
                                   + (e_dhw + e_base) * M.ELEC_PRICE)

    # --- C2: wood occupied + electric frost guard absent
    # electric provides absence frost-guard; stove covers occupied comfort
    c2 = M.simulate(w, q_sol, occ, setpoint_abs=7.0, capacity=M.CAP_STOVE)
    q2_occ = kwh(c2["q_heat"][occ]); q2_abs = kwh(c2["q_heat"][~occ])
    steres2 = q2_occ / (M.STOVE_EFF * M.WOOD_KWH_STERE)
    res["C2 wood+frost"] = dict(freeze_stats(c2["tin"]), heat_kwh=q2_occ + q2_abs,
                                steres=steres2, elec_kwh=q2_abs + e_dhw + e_base,
                                cost=steres2 * M.WOOD_PRICE_STERE
                                     + (q2_abs + e_dhw + e_base) * M.ELEC_PRICE)

    # --- P: pellet stove, programmable: comfort occupied + frost guard absent
    p = M.simulate(w, q_sol, occ, setpoint_abs=7.0, capacity=M.CAP_PELLET)
    kg = kwh(p["q_heat"]) / (M.PELLET_EFF * M.PELLET_KWH_KG)
    on = p["q_heat"] > 0                       # stove electronics: fans, auger, igniter
    start = on & ~np.roll(on, 1); start[0] = on[0]
    e_aux = kwh(on * M.PELLET_EL_RUN
                + start * (M.PELLET_EL_IGN - M.PELLET_EL_RUN) * M.PELLET_IGN_H)
    res["P pellet stove"] = dict(freeze_stats(p["tin"]), heat_kwh=kwh(p["q_heat"]),
                                 pellets_kg=kg, aux_kwh=e_aux,
                                 elec_kwh=e_aux + e_dhw + e_base,
                                 cost=kg * M.PELLET_PRICE_KG
                                      + (e_aux + e_dhw + e_base) * M.ELEC_PRICE)

    # --- D: solar thermal on top of B (DHW first, then space heating support)
    st = solar_thermal(w, el, az, hz, svf)
    dhw = dhw_load(w, occ)
    useful_dhw = np.minimum(st, dhw)
    useful_space = np.minimum(st - useful_dhw, b["q_heat"])
    st_useful = kwh(useful_dhw + useful_space)
    elec_d = res["B electric"]["elec_kwh"] - st_useful
    res["D +solar thermal"] = dict(freeze_stats(b["tin"]),
                                   heat_kwh=res["B electric"]["heat_kwh"],
                                   st_gross=kwh(st), st_useful=st_useful,
                                   elec_kwh=elec_d, cost=elec_d * M.ELEC_PRICE)

    # --- E: heat pump (same comfort as B), resistance backup above capacity
    cap_hp = M.hp_capacity(w["t2m"])
    e = M.simulate(w, q_sol, occ, setpoint_abs=7.0, capacity=None)   # need
    need = e["q_heat"]
    q_hp = np.minimum(need, cap_hp)
    q_bu = need - q_hp
    elec_hp = q_hp / M.hp_cop(w["t2m"]) + q_bu                       # W
    e_hp_kwh = kwh(elec_hp) + e_dhw + e_base
    res["E heat pump"] = dict(freeze_stats(e["tin"]), heat_kwh=kwh(need),
                              elec_kwh=e_hp_kwh, backup_kwh=kwh(q_bu),
                              cost=e_hp_kwh * M.ELEC_PRICE)

    # --- F / F2: PV + battery on top of E — south pan (half roof) or both pans
    tilt = np.degrees(M.ROOF_PITCH)
    pv_s = pv_production(w, el, az, hz, svf, M.PV_KWP_PAN, tilt, 180)   # south pan
    pv_n = pv_production(w, el, az, hz, svf, M.PV_KWP_PAN, tilt, 0)    # north pan
    load = elec_hp + dhw + base
    for name, pv, kwp in (("F PV half roof", pv_s, M.PV_KWP_PAN),
                          ("F2 PV full roof", pv_s + pv_n, 2 * M.PV_KWP_PAN)):
        imp, exp, selfc = battery_dispatch(pv, load)
        bill = imp * M.ELEC_PRICE - exp * M.FEED_IN
        res[name] = dict(freeze_stats(e["tin"]),
                         heat_kwh=res["E heat pump"]["heat_kwh"],
                         pv_kwh=kwh(pv), pv_kwp=kwp,
                         grid_import=imp, export=exp, self_kwh=selfc,
                         elec_kwh=kwh(load), cost=bill)

    # reference: permanently inhabited at 20 C, electric
    r = M.simulate(w, q_sol, np.ones(len(occ), bool), setpoint_abs=20.0,
                   capacity=M.CAP_ELECTRIC)
    e_ref = kwh(r["q_heat"]) + 3.0 * 365 + kwh(np.full(len(occ), 300.0))
    res["Ref always 20C"] = dict(freeze_stats(r["tin"]), heat_kwh=kwh(r["q_heat"]),
                                 elec_kwh=e_ref, cost=e_ref * M.ELEC_PRICE)

    return res, dict(w=w, occ=occ, occ_days=occ_days, tin_free=tin_free,
                     q_sol=q_sol, b=b, pv=pv_s, pv_n=pv_n, st=st, el=el, az=az,
                     hz=hz, svf=svf, need=need, elec_hp=elec_hp, dhw=dhw, base=base)

def report(res, tag):
    print(f"\n=== {tag} ===")
    cols = ["heat_kwh", "elec_kwh", "cost", "t_min", "h_below0", "h_above26"]
    print(f"{'scenario':<18}" + "".join(f"{c:>12}" for c in cols) + "   extras")
    for name, r in res.items():
        row = f"{name:<18}"
        for c in cols:
            v = r.get(c, "")
            row += f"{v:>12.0f}" if isinstance(v, float) else f"{v:>12}"
        extra = []
        for k in ("steres", "pellets_kg", "aux_kwh", "st_useful", "st_gross", "backup_kwh",
                  "pv_kwp", "pv_kwh", "grid_import", "export", "heat_frost", "heat_occ"):
            if k in r:
                extra.append(f"{k}={r[k]:.0f}" if k != "steres" else f"steres={r[k]:.1f}")
        row += "   " + " ".join(extra)
        print(row)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
HORIZONS = [(2026, "now"), (2036, "+10y"), (2046, "+20y"),
            (2056, "+30y"), (2066, "+40y"), (2076, "+50y")]

def day_night_report(slopes):
    """Outdoor day/night temperatures per climate horizon; returns CSV rows."""
    w0 = M.load_tmy()
    rows = [["horizon", "year", "annual_day", "annual_night"]
            + [f"{m}_{k}" for m in MONTHS for k in ("day", "night")]]
    print("\n=== Outdoor day / night temperature, climate horizons (degC) ===")
    print(f"{'horizon':<12}{'annual day':>11}{'annual night':>13}{'Jan day':>9}"
          f"{'Jan night':>10}{'Jul day':>9}{'Jul night':>10}")
    for year, lab in HORIZONS:
        w = M.apply_warming(w0, year, slopes)
        day_m, night_m, day_a, night_a = M.day_night_monthly(w)
        print(f"{lab + f' ({year})':<12}{day_a:>11.1f}{night_a:>13.1f}{day_m[0]:>9.1f}"
              f"{night_m[0]:>10.1f}{day_m[6]:>9.1f}{night_m[6]:>10.1f}")
        rows.append([lab, year, round(day_a, 2), round(night_a, 2)]
                    + [round(v, 2) for pair in zip(day_m, night_m) for v in pair])
    return rows

def pv_roof_report(ctx):
    """Roof area + monthly kWh/day for half (south pan) and full roof; CSV rows."""
    month = ctx["w"]["month"].astype(int)
    pv_half, pv_full = ctx["pv"], ctx["pv"] + ctx["pv_n"]
    ndays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    print(f"\n=== Roof PV potential (pitch {np.degrees(M.ROOF_PITCH):.1f} deg, "
          f"pans face S and N) ===")
    print(f"roof area: {M.A_ROOF:.1f} m2 total, {M.A_ROOF_PAN:.1f} m2 per pan")
    print(f"half roof = south pan: {M.PV_KWP_PAN:.1f} kWp   "
          f"full roof: {2 * M.PV_KWP_PAN:.1f} kWp")
    rows = [["month", "half_roof_kwh_day", "full_roof_kwh_day"]]
    print(f"{'month':<8}{'half kWh/d':>11}{'full kWh/d':>11}")
    for k in range(1, 13):
        h = np.sum(pv_half[month == k]) / 1000.0 / ndays[k - 1]
        f_ = np.sum(pv_full[month == k]) / 1000.0 / ndays[k - 1]
        rows.append([MONTHS[k - 1], round(h, 1), round(f_, 1)])
        print(f"{MONTHS[k - 1]:<8}{h:>11.1f}{f_:>11.1f}")
    h_yr, f_yr = np.sum(pv_half) / 1e3, np.sum(pv_full) / 1e3
    print(f"{'YEAR':<8}{h_yr / 365:>11.1f}{f_yr / 365:>11.1f}   "
          f"({h_yr:.0f} / {f_yr:.0f} kWh/yr; "
          f"{h_yr / M.PV_KWP_PAN:.0f} kWh/kWp south pan)")
    rows.append(["year_total_kwh", round(h_yr), round(f_yr)])
    return rows

def co2_report(res_now, res_end, horizon=50.0):
    """Operational + embodied CO2 per scenario over `horizon` years; CSV rows."""
    import carbon as CB
    g = CB.ELEC_G_KWH[CB.ELEC_DEFAULT]
    g_pel = CB.wood_fuel_g_kwh(CB.PELLET_G_KWH)
    g_log = CB.wood_fuel_g_kwh(CB.WOOD_LOG_G_KWH)

    def op(r):
        # PV scenarios buy only their grid import; the rest is self-consumed
        e = r.get("grid_import", r.get("elec_kwh", 0))
        return (e * g
                + r.get("pellets_kg", 0) * M.PELLET_KWH_KG * g_pel
                + r.get("steres", 0) * M.WOOD_KWH_STERE * g_log) / 1000.0

    equip = {   # scenario -> [(item, kg CO2eq, life years)]
        "P pellet stove": [("pellet stove", CB.PELLET_STOVE_KG, CB.PELLET_STOVE_LIFE)],
        "E heat pump": [("heat pump", CB.HP_KG, CB.HP_LIFE)],
        "F PV half roof": [("heat pump", CB.HP_KG, CB.HP_LIFE),
                           ("PV", M.PV_KWP_PAN * CB.PV_KG_PER_KWP, CB.PV_LIFE),
                           ("battery", 10 * CB.BATT_KG_PER_KWH, CB.BATT_LIFE_CAL)],
        "F2 PV full roof": [("heat pump", CB.HP_KG, CB.HP_LIFE),
                            ("PV", 2 * M.PV_KWP_PAN * CB.PV_KG_PER_KWP, CB.PV_LIFE),
                            ("battery", 10 * CB.BATT_KG_PER_KWH, CB.BATT_LIFE_CAL)],
    }
    print(f"\n=== CO2 ({CB.ELEC_DEFAULT} {g:.0f} g/kWh, pellets {g_pel:.0f} g/kWh, "
          f"biogenic counted {CB.BIOGENIC_COUNTED * 100:.0f} %) ===")
    print(f"{'scenario':<18}{'kg/yr now':>11}{'t use 50y':>11}{'t equip 50y':>13}"
          f"{'t TOTAL 50y':>13}")
    rows = [["scenario", "kg_per_year_now", "t_use_50y", "t_equipment_50y", "t_total_50y"]]
    for name in res_now:
        if name.startswith("Ref"):
            continue
        o_now, o_end = op(res_now[name]), op(res_end[name])
        use = horizon * (o_now + o_end) / 2 / 1000.0
        emb = CB.embodied_over_horizon(equip.get(name, []), horizon)[1] / 1000.0
        if name.startswith(("E", "F")):
            emb += CB.refrigerant_kg(horizon=horizon) / 1000.0
        print(f"{name:<18}{o_now:>11.0f}{use:>11.1f}{emb:>13.1f}{use + emb:>13.1f}")
        rows.append([name, round(o_now), round(use, 2), round(emb, 2),
                     round(use + emb, 2)])
    return rows

if __name__ == "__main__":
    import csv
    os.makedirs(OUT, exist_ok=True)
    slopes = M.monthly_warming_slopes()

    all_res = {}
    for year, lab in HORIZONS:
        res, ctx = run(lab, year=year, slopes=slopes)
        all_res[(year, lab)] = res
        report(res, f"{lab} ({year}) - occupied {ctx['occ_days']} days/yr")
        if lab == "now":
            ctx_now = ctx

    dn_rows = day_night_report(slopes)
    pv_rows = pv_roof_report(ctx_now)
    co2_rows = co2_report(all_res[HORIZONS[0]], all_res[(2076, "+50y")])

    with open(os.path.join(OUT, "scenarios.csv"), "w", newline="") as f:
        wcsv = csv.writer(f)
        keys = ["scenario", "horizon", "year", "heat_kwh", "elec_kwh", "cost_chf",
                "t_min", "h_below0", "h_below5", "t_max", "h_above26"]
        wcsv.writerow(keys)
        for (year, lab), rr in all_res.items():
            for name, r in rr.items():
                wcsv.writerow([name, lab, year]
                              + [round(r.get(k.replace("cost_chf", "cost"), 0), 1)
                                 for k in keys[3:]])
    for fname, rows in (("daynight.csv", dn_rows), ("pv_roof.csv", pv_rows),
                        ("co2.csv", co2_rows)):
        with open(os.path.join(OUT, fname), "w", newline="") as f:
            csv.writer(f).writerows(rows)
    print(f"\nsaved scenarios.csv, daynight.csv, pv_roof.csv, co2.csv in {OUT}")
