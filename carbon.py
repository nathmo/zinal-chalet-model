"""CO2 accounting for the Zinal chalet: operational emissions and embodied
emissions of the equipment over a 50-year horizon.

All factors are kg CO2eq (GWP100). Every value here is a default that the
dashboard exposes for editing — the point is to make the assumptions visible,
not to pretend they are exact.

ELECTRICITY (g CO2eq/kWh)
  The number you should use depends on the question you are asking:
  - 12   Valais hydro, the standard local product (run-of-river + storage LCA,
         4-25 g/kWh depending on the dam's construction emissions amortization)
  - 30   Swiss *production* mix (hydro + nuclear)
  - 100  Swiss *consumption* mix incl. imports (~98 g/kWh, Sciencedirect 2024;
         KBOB/ecoinvent quote 128 g/kWh for the same idea)
  - 400  European marginal winter generation — arguably the honest number for
         "one more kWh drawn on a January evening", when Switzerland imports
  Default: the Valais product, with the marginal figure offered as a stress test.

WOOD PELLETS
  35 g CO2eq/kWh of fuel is the Swiss supply-chain figure (proPellets.ch, from
  KBOB LCA data): harvesting, drying, pelletizing, transport. It counts the
  biogenic CO2 that leaves the chimney as ZERO, on the assumption that the
  forest regrows and reabsorbs it.
  That assumption is the whole debate. Burning pellets releases ~390 g CO2/kWh
  at the stack. If the wood is not regrown -- or is regrown over 60-100 years,
  which is longer than the horizon we care about -- part of that is a real
  addition to the atmosphere ("carbon debt"). BIOGENIC_COUNTED lets you count a
  fraction of it:
    0.0  standard accounting, sustainably managed forest, residues/thinnings
         (defensible for Swiss pellets: sawmill by-products, short transport)
    0.2  a plausible debt for well-managed but slow-regrowing forest over 50 y
    0.5+ pellets from whole trees / imported / poorly regulated sourcing
  Default 0.0 to match the published Swiss figure; change it to see the risk.

EQUIPMENT
  Embodied emissions of manufacture, amortized by replacing each item when it
  reaches the end of its life within the 50-year window.
"""

import math

# ---------------------------------------------------------------- operational
ELEC_G_KWH = {
    "Valais hydro (local product)": 12.0,
    "Swiss production mix": 30.0,
    "Swiss consumption mix (incl. imports)": 100.0,
    "European marginal (winter imports)": 400.0,
}
ELEC_DEFAULT = "Valais hydro (local product)"

PELLET_G_KWH = 35.0      # supply chain, biogenic counted as neutral (proPellets.ch/KBOB)
WOOD_LOG_G_KWH = 14.0    # split logs, short transport, less processing than pellets
BIOGENIC_G_KWH = 390.0   # CO2 actually leaving the chimney per kWh of wood fuel
BIOGENIC_COUNTED = 0.0   # fraction of the above charged to the house (see docstring)

# ---------------------------------------------------------------- embodied
# (kg CO2eq per unit, expected service life in years)
PV_KG_PER_KWP = 700.0    # rooftop mono-Si, incl. mounting + one inverter swap
PV_LIFE = 30.0           # module warranty/market lifetime
BATT_KG_PER_KWH = 60.0   # LFP cell+pack, 2024 median (Nature Comms: 54/62/69 kg)
BATT_LIFE_CAL = 15.0     # calendar life
BATT_CYCLE_LIFE = 6000.0 # full equivalent cycles to 80 % capacity (LFP)
HP_KG = 1500.0           # domestic air-source unit, manufacture
HP_LIFE = 18.0
HP_REFRIG_KG = 1.2       # refrigerant charge
HP_REFRIG_GWP = 3.0      # R290 propane (R32 = 675, R410A = 2088)
HP_LEAK_YR = 0.02        # annual leak rate
HP_LEAK_EOL = 0.15       # fraction lost at end of life despite recovery
PELLET_STOVE_KG = 400.0  # steel body, auger, electronics
PELLET_STOVE_LIFE = 15.0
HORIZON_Y = 50.0


def battery_life(cycles_per_year, cal_life=BATT_LIFE_CAL, cycle_life=BATT_CYCLE_LIFE):
    """Effective battery life (years): whichever runs out first, calendar or cycles."""
    if cycles_per_year <= 0:
        return cal_life
    return min(cal_life, cycle_life / cycles_per_year)


def units_needed(life_y, horizon=HORIZON_Y):
    """How many times the item must be bought to cover the horizon."""
    return math.ceil(horizon / max(life_y, 0.5))


def embodied_over_horizon(items, horizon=HORIZON_Y):
    """items: list of (name, kg_per_unit, life_years). Returns (rows, total_kg).

    Each row: name, kg per unit, life, units bought over the horizon, total kg.
    """
    rows, total = [], 0.0
    for name, kg, life in items:
        if kg <= 0:
            continue
        n = units_needed(life, horizon)
        t = n * kg
        rows.append(dict(item=name, kg_per_unit=kg, life_y=life, units=n, total_kg=t))
        total += t
    return rows, total


def refrigerant_kg(charge=HP_REFRIG_KG, gwp=HP_REFRIG_GWP, leak_yr=HP_LEAK_YR,
                   eol=HP_LEAK_EOL, life=HP_LIFE, horizon=HORIZON_Y):
    """CO2eq of refrigerant leakage over the horizon (operating + end of life)."""
    annual = charge * leak_yr * gwp
    n = units_needed(life, horizon)
    return annual * horizon + n * charge * eol * gwp


def wood_fuel_g_kwh(base_g_kwh, biogenic_counted=BIOGENIC_COUNTED,
                    biogenic=BIOGENIC_G_KWH):
    """Effective factor for a wood fuel, including any counted carbon debt."""
    return base_g_kwh + biogenic_counted * biogenic
