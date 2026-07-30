# Zinal chalet thermal model

Hourly thermal model of a **timber chalet in Zinal (Val d'Anniviers, Valais,
Switzerland)** — real terrain, mountain-horizon shading, and climate data for the
valley, at village resolution.

> **Location resolution.** The site is a 1 km grid point (46.13 N, 7.63 E, ~1680 m)
> on the east flank of the valley — deliberately not a specific address. The
> building below is a *typical* 1960s-70s Anniviers chalet; treat the dimensions and
> U-values as a plausible archetype, and re-run with your own if you adapt it.

## The building (as modeled)

| item | value | source |
|---|---|---|
| location | 46.13 N, 7.63 E, **~1680 m** (village grid point) | PVGIS |
| terrain | 21.5 % slope, falls to the west | swisstopo (4-point gradient) |
| footprint | 10 m (N-S) x 6 m (E-W) | typical for the valley |
| storeys | 1 full storey + **one attic room under the roof** | assumption |
| heated | ~72 m2, ~175 m3 | assumption |
| roof | 2 pans, **ridge E-W → pans face S and N**, 45 % (24.2 deg) | RCCZ Anniviers Art. 109: 40-50 % |
| walls | 13 cm wood + 7 cm glass wool → U = 0.33 | era-typical build-up |
| roof build-up | 13 cm wood + 20 cm insulation → U = 0.16 | era-typical build-up |
| windows | 3 on the first floor (2 W + 1 S, ~1.4 m2) + 1 attic (W gable, ~1.0 m2), U = 2.8, g = 0.70 | era assumption |
| infiltration | 0.45 air changes/h | assumption (older envelope) |
| heat-loss coeff. | **H = 115 W/K**, time constant ~35 h | computed |

## Data in `data/`

- `horizon.json` — PVGIS DEM horizon: the mountains block the low sun on both sides.
  At winter solstice the sun is above the local horizon only a few hours around noon.
- `tmy.json` — PVGIS typical meteorological year, hourly. **T2m is bias-corrected in
  `load_tmy()`**: the PVGIS grid cell sits well above the valley floor and runs
  several K too cold; each month's mean is shifted onto the ERA5
  elevation-corrected observation (2015-2025). Irradiance is satellite-based and
  kept as-is. Corrected temperatures ≈ 2020 climate.
- `archive.json` — ERA5 daily means 2015-2025 for the valley (annual mean +4.1 °C)
- `climate.json` — CMIP6-HighRes daily means 2026-2050, 3 models
- `climate_minmax.json` — same, daily max/min → separate **day and night** warming trends

## Climate: day / night temperatures, now → +50 years

Warming trends are fitted per month on the CMIP6-HighRes 3-model mean (2026-2050,
extrapolated linearly beyond): **mean +0.47 K/decade, days +0.39, nights +0.58** —
nights warm faster, January fastest (+1.3 K/decade). Every simulation shifts each
hour with its month's day- or night-trend (day = sun above horizon).

| horizon | annual day | annual night | Jan day | Jan night | Jul day | Jul night |
|---|---|---|---|---|---|---|
| now (2026) | 6.7 | 2.2 | −3.6 | −4.6 | 15.3 | 12.3 |
| +10 y (2036) | 7.0 | 2.8 | −2.5 | −3.0 | 15.2 | 12.6 |
| +20 y (2046) | 7.4 | 3.4 | −1.4 | −1.5 | 15.0 | 12.9 |
| +30 y (2056) | 7.8 | 4.1 | −0.3 | 0.1 | 14.9 | 13.2 |
| +40 y (2066) | 8.1 | 4.7 | 0.8 | 1.7 | 14.8 | 13.5 |
| +50 y (2076) | 8.5 | 5.3 | 1.9 | 3.2 | 14.7 | 13.8 |

(Monthly detail in `out/daynight.csv`; Jul day/night look flat because July warms
slowest in these models while winter warms fastest.)

## Roof PV potential

Roof surface: **65.8 m2 total, 32.9 m2 per pan** (pitch 24.2°). With 425 Wp modules
(15 per pan): **half roof = south pan = 6.4 kWp**, full roof = 12.8 kWp.
Mountain horizon, snow albedo (Nov-Apr) and PR 0.80 included.

| | half roof (south pan) | full roof (S + N pans) |
|---|---|---|
| year | **5 680 kWh** (890 kWh/kWp) | **9 950 kWh** |
| average | 15.6 kWh/day | 27.3 kWh/day |
| December | 3.7 kWh/day | 6.2 kWh/day |
| July | 29.3 kWh/day | 53.6 kWh/day |

The south pan alone produces ~2× the house's entire heat-pump electricity demand —
but mostly in the wrong season (Dec-Feb PV ≈ 4-5 kWh/day vs winter demand ~22 kWh/day).
The north pan adds 75 % more energy, nearly all of it in summer (isotropic-sky model;
its winter share is optimistic). Monthly detail: `out/pv_roof.csv`.

## Headline results — now (2026 climate), comfort 20 °C occupied / 7 °C frost guard

All rows include the non-heating electricity: **plugs 300 W when present / 20 W
standby when empty (≈ 670 kWh/yr) + DHW 3 kWh/occupied day (≈ 220 kWh/yr)**.

| scenario | energy bought | cost/yr | notes |
|---|---|---|---|
| A do nothing | 890 kWh el | 242 CHF | indoor hits **−15 °C**; 2 100 h/yr below 0 °C — pipes freeze |
| B electric heaters | 7 090 kWh el | 1 913 CHF | frost guard alone is 3 450 kWh |
| C wood only | 3.4 steres + 890 kWh | 712 CHF | cheapest, but **must drain water when leaving** |
| C2 wood + el. frost guard | 2.3 steres + 4 380 kWh | 1 504 CHF | |
| P pellet stove (programmed) | 1 490 kg + 1 280 kWh | 1 062 CHF | one appliance covers comfort **and** frost guard; needs 389 kWh/yr of electronics |
| D + 4 m2 solar thermal | | 1 871 CHF | only **159 kWh/yr useful** — not worth it |
| E air-source heat pump | 3 680 kWh el | 994 CHF | COP-weighted, incl. cold-day backup |
| F HP + PV **half roof** (6.4 kWp) + 10 kWh batt | 2 365 kWh net | **209 CHF** | south pan; export 4 300 kWh |
| F2 HP + PV **full roof** (12.8 kWp) + 10 kWh batt | 2 030 kWh net | **−274 CHF** (earns) | at 0.10 CHF/kWh feed-in |
| Ref: inhabited full-time | 15 860 kWh | 4 282 CHF | context if it ever becomes a primary home |

The south-facing roof (corrected orientation) + corrected valley temperatures change
the picture vs the earlier model: heating demand roughly halves, PV yield per kWp
rises from ~810 to ~920 kWh/kWp, and a full-roof system becomes a small net earner.

## Climate horizons (all scenarios in `out/scenarios.csv`)

| | now | +10 y | +20 y | +30 y | +40 y | +50 y |
|---|---|---|---|---|---|---|
| B electric, kWh bought | 7 090 | 6 740 | 6 400 | 6 070 | 5 750 | 5 460 |
| E heat pump, kWh el | 3 680 | 3 510 | 3 350 | 3 200 | 3 060 | 2 940 |
| E heat pump, CHF/yr | 994 | 949 | 906 | 865 | 827 | 793 |
| F2 full roof, CHF/yr | −274 | −312 | −346 | −377 | −406 | −433 |
| A free-float: h < 0 °C | 2 118 | 1 723 | 1 422 | 1 210 | 935 | 711 |
| A free-float: min °C | −15 | −14 | −14 | −13 | −13 | −12 |

Heating −25 % by 2076, but the frost problem never goes away: an unheated house
still spends ~700 h/yr below 0 °C in 2076. Indoor hours above 26 °C stay at **0**
through 2076 — no cooling needed, a fan for the odd afternoon is plenty.

Arrival warm-up (12 kW stove+heaters): from a cold soak ~11 h to 18 °C (walls must
warm, not just air); from the 7 °C frost guard ~5 h.

## CO₂ — yearly use and 50-year impact

Factors live in `carbon.py`, all editable in the dashboard. Defaults: **Valais hydro
12 g CO₂eq/kWh** (the standard local product; Swiss consumption mix incl. imports is
~100, European marginal winter generation ~400 — both selectable), **pellets 35 g/kWh
of fuel** (proPellets.ch / KBOB: harvesting, drying, pelletizing, transport),
firewood 14 g/kWh.

**Is wood net zero?** The 35 g/kWh figure counts the chimney's biogenic CO₂ as zero,
assuming the forest regrows. The stack actually emits ~390 g/kWh. For Swiss pellets
made of sawmill by-products with short transport that assumption is defensible; for
whole-tree or imported pellets it is not, and regrowth takes 60-100 years — longer
than the horizon that matters. The dashboard has a **"biogenic CO₂ counted" slider**:
at 25 % the pellet scenario goes from 13 to 43 t CO₂ over 50 years, i.e. from best to
worst. This is the single most consequential assumption in the whole model.

50-year totals with default factors (2026 → 2076 climate, declining heating included):

| scenario | kg CO₂/yr now | t use (50 y) | t equipment (50 y) | **t total** |
|---|---|---|---|---|
| A do nothing | 11 | 0.5 | 0 | **0.5** |
| B electric heaters | 85 | 3.8 | 0 | **3.8** |
| C wood only | 91 | 4.2 | 0 | **4.2** |
| C2 wood + frost guard | 107 | 4.8 | 0 | **4.8** |
| E air-source heat pump | 44 | 2.0 | 4.5 | **6.5** |
| P pellet stove | 266 | 11.6 | 1.6 | **13.2** |
| F HP + PV half roof + battery | 28 | 1.2 | 15.8 | **17.1** |
| F2 HP + PV full roof + battery | 24 | 1.1 | 24.8 | **25.8** |

**On Valais hydro, adding hardware costs more carbon than it saves.** Local
electricity is already ~12 g/kWh, so a PV+battery system (700 kg CO₂eq/kWp over
30 y, LFP 60 kg/kWh over 15 y, both rebought inside 50 years) never pays back its
own manufacture — it saves ~0.8 t of use-phase CO₂ and costs ~11 t to build.
Switch the sidebar to the Swiss consumption mix or the European marginal factor and
the ranking flips: at 400 g/kWh the heat pump's use-phase alone is 66 t and PV
becomes strongly worth building. **Which number is right depends on whether you
think your Valais hydro contract is physically real in a January cold snap.**

Equipment lifetimes: PV 30 y, heat pump 18 y (+ refrigerant leakage — negligible for
R290 at GWP 3, ~1 t over 50 y if it were R32 at GWP 675), pellet stove 15 y.
**The LFP battery is calendar-limited, not cycle-limited**: this house only puts
~70 cycles/yr through it against a 6 000-cycle rating (85 years' worth), so it dies
of old age at ~15 years — sizing it bigger buys nothing in carbon terms.

## Natural hazards

The slope above Zinal is largely covered by cantonal avalanche danger zones (blue,
with red zones upslope) and red torrent/debris-flow corridors; all of Valais is in
seismic zone Z3b. Method, village-level picture, 50-year probabilities and sources
in [`HAZARDS.md`](HAZARDS.md) (checked 30.07.2026) — any specific building needs its
own point query.

## Interactive dashboard

```
streamlit run app.py
```

- interactive **3D scene** (rotate/zoom): house, terrain, mountain-horizon wall and
  the sun paths for the solstices/equinox with visible vs blocked segments
- hourly **indoor + outdoor temperature** over the year, for any horizon
  (2026 / 2036 / 2046 / 2056 / 2066 / 2076); presence periods shaded
- daily view: per-day **mean ±1σ/2σ/3σ** bands (spread of each day's 24 hourly values)
- **electricity flows**: annual Sankey (PV → direct use / battery / export, grid,
  battery losses) + daily stacked areas of usage by end use (heating, DHW,
  plugs/standby) and by source (PV, battery, grid, export); the load is
  presence-aware (plugs when there vs standby when empty), dispatched against any
  enabled heating scenario
- scenarios toggle on/off and update the indoor temperature: free-float, electric,
  wood only, wood+frost guard, **programmable pellet stove (comfort + frost guard)**,
  heat pump; PV half/full roof affects the cost table
- **every assumption is editable** in the sidebar (comfort setpoints, fabric U-values,
  ACH, thermal mass, window areas, system capacities, COP curve, pellet stove,
  PV modules & PR, battery, prices, investment costs & lifetimes) and echoed in a
  summary table; investment is amortized straight-line over the lifetime
- **CO₂ section**: yearly emissions and the 50-year total, broken down by source —
  grid electricity, pellet/firewood supply chain, unregrown biogenic carbon, and the
  manufacture of PV, battery, heat pump, pellet stove plus refrigerant leakage, with
  replacements counted whenever an item wears out inside the horizon
- **off-grid switch** (PV + battery, no grid): a coupled thermal/electrical
  simulation where heating only runs if PV + battery can power it — electric
  heating and the heat pump fail for long winter stretches, and even the pellet
  stove stops when its electronics (100 W running, 500 W for 15 min at ignition)
  cannot be supplied. Shows unserved kWh, curtailed PV, and the resulting cold drift
- **presence calendar, fully explicit in the sidebar**: the default entries
  (Christmas, February week, summer — each removable/editable) plus a weekend rule
  (every / every-other weekend, month selection) and custom date ranges
  (ranges may wrap the year end)

## Files

- `HAZARDS.md` — natural hazard assessment (avalanche, torrent, seismic, …) at the exact location
- `app.py` — the Streamlit dashboard (needs `streamlit` + `plotly`)
- `scene3d.py` — the interactive plotly 3D scene used by the dashboard
- `carbon.py` — CO₂ factors (electricity, wood fuels, embodied equipment) + lifetimes,
  with the sources and the biogenic-carbon caveat documented inline
- `model.py` — constants, weather loaders (incl. TMY bias correction), solar geometry +
  horizon masking, day/night warming trends, 1-node RC model
- `simulate.py` — occupancy calendar (~74 d/yr) + scenarios × 6 climate horizons;
  writes `out/scenarios.csv`, `out/daynight.csv`, `out/pv_roof.csv`
- `make_plots.py` — sun-path, monthly energy, cost, free-float, day/night, roof-PV figures
- `render3d.py` — 3D scene (house, terrain, horizon wall, sun paths); `--show` for interactive

Run: `python simulate.py && python make_plots.py && python render3d.py` (needs numpy + matplotlib).

## Main modeling assumptions to keep in mind

- Single thermal zone, effective capacity 4.0 kWh/K (light timber, interior insulation)
- Attic room geometry is an estimate (~20 m2 usable of the 30 m2 attic level)
- Windows-era U-value, sizes and ACH are estimates; a blower test or window label would refine them
- The TMY diurnal cycle comes from a coarse grid cell and likely under-states the
  valley's day-night swing; day/night *means* are anchored on ERA5 observations
- Beyond 2050 the CMIP6 trend is extrapolated linearly (≈ moderate-emissions path)
- PV: isotropic sky, PR 0.80, no snow-cover blackout on the panels (winter yield of
  both pans, especially the north one, is somewhat optimistic)
- Occupancy calendar is configurable in `simulate.py` (`occupancy()`)
- Non-heating electricity is presence-aware and counted in every scenario:
  plugs/fridge/router 300 W when someone is there, 20 W standby when empty,
  DHW 3 kWh per occupied day
- The pellet stove is **not** electricity-free: 100 W while burning plus 500 W for
  15 min at each ignition — 386 kWh/yr over 3 750 burning hours and ~107 starts.
  A power cut therefore stops it (matters only off-grid or during an outage)
- Prices: 0.27 CHF/kWh electricity, 140 CHF/stere, 0.10 CHF/kWh feed-in — edit in `model.py`
