"""2D figures: sun path vs mountain horizon, monthly energy, costs, free-float temp."""
import numpy as np
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import model as M
import simulate as S

OUT = S.OUT
os.makedirs(OUT, exist_ok=True)

# reference palette (dataviz skill), light mode
SURF = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"
GRID = "#e1e0d9"; BASE = "#c3c2b7"
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "text.color": INK, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.family": "sans-serif", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})

SLOPES = M.monthly_warming_slopes()
res, ctx = S.run("now", year=2026, slopes=SLOPES)
w, occ, hz = ctx["w"], ctx["occ"], ctx["hz"]
month = w["month"].astype(int)

def monthly(x, mask=None):
    m = np.ones(len(x), bool) if mask is None else mask
    return np.array([np.sum(x[(month == k) & m]) / 1000.0 for k in range(1, 13)])

MON = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]

# ---------------------------------------------------------------- 1. sun path vs horizon
fig, ax = plt.subplots(figsize=(9, 4.6))
azg = np.linspace(45, 315, 400)
ax.fill_between(azg, 0, hz(azg), color="#d8d7d0", zorder=1)
ax.plot(azg, hz(azg), color=MUTED, lw=1.2, zorder=2)
dates = [(355, "21 Dec", C1), (80, "21 Mar", C2), (172, "21 Jun", C3)]
for doy, lab, col in dates:
    hrs = np.arange(0, 24, 0.1)
    el, az = M.sun_position(np.full_like(hrs, doy), hrs)
    keep = el > -2
    el, az, hrs_k = el[keep], az[keep], hrs[keep]
    o = np.argsort(az)
    el, az, hrs_k = el[o], az[o], hrs_k[o]
    vis = el > hz(az)
    ax.plot(az, np.where(vis, el, np.nan), color=col, lw=2.2, zorder=4)
    ax.plot(az, np.where(~vis, el, np.nan), color=col, lw=1.1, ls=(0, (2, 3)),
            alpha=0.55, zorder=3)
    # hour dots (local winter time UTC+1)
    for h in range(6, 20):
        i = np.argmin(np.abs(hrs_k - (h - 1)))
        if el[i] > 0:
            ax.plot(az[i], el[i], "o", ms=4, color=col, zorder=5)
            if doy == 172 and h in (7, 10, 13, 16, 19) or doy == 355 and h in (10, 14):
                ax.annotate(f"{h}h", (az[i], el[i]), textcoords="offset points",
                            xytext=(0, 7), ha="center", fontsize=8, color=INK2)
    lab_i = np.argmax(el)
    ax.annotate(lab, (az[lab_i], el[lab_i] + 3.2), ha="center", fontsize=10,
                color=col, fontweight="bold")
ax.annotate("mountains (Besso side)", (95, 12), fontsize=9, color=INK2)
ax.annotate("mountains\n(Sorebois side)", (275, 12), fontsize=9, color=INK2, ha="center")
ax.set_xticks([90, 135, 180, 225, 270], ["E", "SE", "S", "SW", "W"])
ax.set_xlim(60, 300); ax.set_ylim(0, 74)
ax.set_ylabel("elevation above horizon (°)")
ax.set_title("Sun paths over the local mountain horizon — Zinal, ~1680 m\n"
             "solid = sun visible, dotted = blocked by terrain  (dots = full hours, local winter time)",
             fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "sunpath.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 2. monthly energy
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.4))
x = np.arange(12)
q = ctx["b"]["q_heat"]
occ_m = monthly(q, occ); frost_m = monthly(q, ~occ)
ax1.bar(x, occ_m, 0.62, color=C1, label="heating while occupied (20 °C)")
ax1.bar(x, frost_m, 0.62, bottom=occ_m, color=C2,
        label="frost-guard while empty (7 °C)", edgecolor=SURF, linewidth=2)
for i in range(12):
    t = occ_m[i] + frost_m[i]
    if t > 40:
        ax1.annotate(f"{t:.0f}", (i, t), textcoords="offset points", xytext=(0, 3),
                     ha="center", fontsize=8, color=INK2)
ax1.set_xticks(x, MON); ax1.set_ylabel("kWh / month")
ax1.set_title("Monthly heating need — electric scenario (secondary-home calendar, 74 days occupied)",
              fontsize=10, color=INK)
ax1.legend(frameon=False, fontsize=9)

pv_half_m = monthly(ctx["pv"])
pv_full_m = monthly(ctx["pv"] + ctx["pv_n"])
load_m = monthly(ctx["elec_hp"] + ctx["dhw"] + ctx["base"])
ax2.plot(x, load_m, color=C1, lw=2.2, marker="o", ms=5, label="electricity demand (heat pump + DHW + plugs)")
ax2.plot(x, pv_half_m, color=C4, lw=2.2, marker="o", ms=5,
         label=f"PV half roof — south pan, {M.PV_KWP_PAN:.1f} kWp")
ax2.plot(x, pv_full_m, color=C4, lw=1.6, ls=(0, (4, 3)), marker="o", ms=4,
         label=f"PV full roof — both pans, {2 * M.PV_KWP_PAN:.1f} kWp")
ax2.set_xticks(x, MON); ax2.set_ylabel("kWh / month"); ax2.set_ylim(0, None)
ax2.set_title("The winter mismatch: PV vs demand", fontsize=10, color=INK)
ax2.legend(frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "energy.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 3. annual cost comparison
fig, ax = plt.subplots(figsize=(9, 3.8))
names = ["B electric", "C wood only", "C2 wood+frost", "P pellet stove",
         "D +solar thermal", "E heat pump", "F PV half roof", "F2 PV full roof"]
labels = ["Electric heaters", "Wood stove only*", "Wood + frost guard",
          "Pellet stove (programmed, comfort + frost guard)",
          "Electric + solar thermal", "Air-source heat pump",
          "Heat pump + PV half roof (6.4 kWp) + battery",
          "Heat pump + PV full roof (12.8 kWp) + battery"]
vals = [res[n]["cost"] for n in names]
o = np.argsort(vals)[::-1]
y = np.arange(len(names))
ax.barh(y, [vals[i] for i in o], 0.6, color=C1)
ax.axvline(0, color=BASE, lw=1)
ax.set_yticks(y, [labels[i] for i in o])
for j, i in enumerate(o):
    ax.annotate(f"{vals[i]:,.0f} CHF", (max(vals[i], 0), j), textcoords="offset points",
                xytext=(6, 0), va="center", fontsize=9, color=INK2)
ax.set_xlim(min(0, min(vals) * 1.3), max(vals) * 1.18)
ax.set_xlabel("running cost, CHF / year (energy only, no investment)")
ax.set_title("Annual running cost — same comfort (20 °C occupied, 7 °C frost guard)\n"
             f"*wood only: no frost protection, interior hits {res['C wood only']['t_min']:.0f} °C — drain the pipes",
             fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "costs.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 4. free-float temperature
fig, ax = plt.subplots(figsize=(9, 4.2))
days = np.arange(365)
tin_d = ctx["tin_free"][:8760].reshape(365, 24)
tout_d = w["t2m"][:8760].reshape(365, 24)
ax.fill_between(days, tin_d.min(1), tin_d.max(1), color=C1, alpha=0.25, lw=0)
ax.plot(days, tin_d.mean(1), color=C1, lw=1.8, label="indoor, no heating (daily range)")
ax.plot(days, tout_d.mean(1), color=MUTED, lw=1.2, label="outdoor (daily mean)")
ax.axhline(0, color=C2, lw=1.2, ls=(0, (4, 3)))
ax.annotate("0 °C — pipes freeze", (185, 0.8), fontsize=9, color=C2)
mstart = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30])
ax.set_xticks(mstart, MON); ax.set_xlim(0, 364)
ax.set_ylabel("temperature (°C)")
ax.set_title("Scenario A, do nothing: indoor temperature free-floats\n"
             f"house spends {np.sum(ctx['tin_free'] < 0):,} h/yr below 0 °C — max summer indoor "
             f"{ctx['tin_free'].max():.0f} °C (no cooling problem)", fontsize=10, color=INK)
ax.legend(frameon=False, fontsize=9, loc="upper left")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "freefloat.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 5. day/night temps, now vs +50y
fig, ax = plt.subplots(figsize=(9, 4.4))
w0 = M.load_tmy()
for year, col in [(2026, C1), (2076, C2)]:
    ww = M.apply_warming(w0, year, SLOPES)
    day_m, night_m, day_a, night_a = M.day_night_monthly(ww)
    ax.plot(np.arange(12), day_m, color=col, lw=2.2, marker="o", ms=5)
    ax.plot(np.arange(12), night_m, color=col, lw=1.6, ls=(0, (4, 3)), marker="o", ms=4)
    dodge = max(0.0, (1.4 - (day_m[-1] - night_m[-1])) / 2)   # keep end labels apart
    ax.annotate(f"{year} day", (11.15, day_m[-1] + dodge), color=col, fontsize=9,
                fontweight="bold", va="center")
    ax.annotate(f"{year} night", (11.15, night_m[-1] - dodge), color=col,
                fontsize=9, va="center")
ax.axhline(0, color=MUTED, lw=1, ls=(0, (4, 3)))
ax.set_xticks(np.arange(12), MON); ax.set_xlim(-0.3, 13.2)
ax.set_ylabel("outdoor temperature (°C)")
ax.set_title("Day (solid) and night (dashed) outdoor temperature — now vs +50 years\n"
             "CMIP6-HighRes trends: nights warm faster "
             f"(+{np.mean(SLOPES['night']) * 10:.1f} K/decade) than days "
             f"(+{np.mean(SLOPES['day']) * 10:.1f} K/decade)", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "daynight.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 6. roof PV: kWh/day by month
fig, ax = plt.subplots(figsize=(9, 4.2))
ndays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
half_d = monthly(ctx["pv"]) / ndays
north_d = monthly(ctx["pv_n"]) / ndays
ax.bar(np.arange(12), half_d, 0.62, color=C4,
       label=f"south pan (half roof, {M.PV_KWP_PAN:.1f} kWp)")
ax.bar(np.arange(12), north_d, 0.62, bottom=half_d, color=C1,
       label=f"+ north pan (full roof, {2 * M.PV_KWP_PAN:.1f} kWp)",
       edgecolor=SURF, linewidth=2)
for i in range(12):
    ax.annotate(f"{half_d[i] + north_d[i]:.0f}", (i, half_d[i] + north_d[i]),
                textcoords="offset points", xytext=(0, 3), ha="center",
                fontsize=8, color=INK2)
ax.set_xticks(np.arange(12), MON)
ax.set_ylabel("kWh / day")
ax.set_title(f"PV production per day — roof {M.A_ROOF:.0f} m² total, pitch 24°, pans face S/N\n"
             f"year: {np.sum(ctx['pv']) / 1e3:.0f} kWh (half) / "
             f"{np.sum(ctx['pv'] + ctx['pv_n']) / 1e3:.0f} kWh (full) — "
             "mountain horizon + snow albedo included", fontsize=10, color=INK)
ax.legend(frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "pvroof.png"), dpi=150); plt.close(fig)

print("saved sunpath.png energy.png costs.png freefloat.png daynight.png pvroof.png in", OUT)
