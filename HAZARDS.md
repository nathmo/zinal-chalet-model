# Natural hazard context — Zinal (Val d'Anniviers, VS)

Checked **30.07.2026** for a chalet site in Zinal, at village resolution
(~1680 m, east flank of the valley). This documents the *method* and the
*village-level* picture; anyone assessing a specific building must redo the
point queries for their own parcel, because the zones change over a few tens of
metres.

**TL;DR: this part of the valley is not hazard-free.** Chalets on the slope
above the village commonly sit **inside the avalanche danger zone "moyen"
(blue)** of the canton Valais hazard map, with **red zones (danger élevé)
upslope** and **red torrent/debris-flow corridors** following the couloirs down
to the Navisence. Rockfall, landslide, river flooding, surface runoff and
permafrost are generally clear at village altitude. The whole of Valais is in
**seismic zone Z3b, the highest in Switzerland**.

## Method (reproducible for any site)

Point queries at the building coordinate, not just visual map reading:

- **Canton VS hazard map** (the legally relevant *carte des dangers*, canton is
  data owner) via the geodienste.ch WMS
  `https://geodienste.ch/db/gefahrenkarten_v1_3_0/deu` — GetFeatureInfo on the
  `gefahrengebiet_*` layers per process, with point-in-polygon verification of
  the returned zone geometries and distance-to-boundary computation.
- **Federal geoportal** (api3/wms.geo.admin.ch): SilvaProtect-CH indication
  layers (avalanche, rockfall, hillslope debris flow, debris flow, sediment
  deposition), Aquaprotect 50/100/250/500 floods, surface-runoff hazard map,
  permafrost, 50-year hail, SIA 261 seismic zones, historical earthquakes.
- **RDPPF cadastre extract** (rdppf.apps.vs.ch). Caveat: the danger-zone theme
  is **not yet published in the RDPPF for Anniviers** — the extract is silent on
  hazards and must not be read as a clean bill of health; the cantonal hazard
  map above is the authoritative source.

## Processes, at village level

| process | source | picture in Zinal |
|---|---|---|
| **avalanche** | VS carte des dangers | blue and red zones cover much of the slope above the village; the boundary between them can run within a few tens of metres of individual buildings |
| **torrent / debris flow** | VS carte des dangers | red corridors along the couloirs (e.g. Torrent des Bondes) crossing towards the river |
| landslide | VS carte des dangers | scattered yellow zones, generally not at the village |
| rockfall | VS carte des dangers | not mapped in the village area |
| river flooding (Navisence) | VS + Aquaprotect | confined to the valley floor along the river |
| surface runoff | BAFU | largely unmapped at this altitude |
| permafrost | BAFU | none at village altitude (present far upslope in the catchment) |
| hail | MeteoSwiss | 50-yr reference hailstone ~2.5 cm — minor; PV modules are rated for it |
| **earthquake** | SIA 261 | **zone Z3b — highest in Switzerland** (M 6.2 Visp 1855, M 5.8 Sierre 1946, both within ~30 km) |

## Risk over a 50-year horizon

**Avalanche dominates.** A blue zone means avalanches with return periods of
roughly 30–300 years and impact pressures below 30 kPa can reach the site.
Probability of at least one event in 50 years, by effective return period T,
is 1 − (1 − 1/T)^50:

| effective T | 30 y | 100 y | 300 y |
|---|---|---|---|
| P(≥1 impact in 50 y) | 81 % | 39 % | 15 % |

For a building just inside a blue zone, "a few tens of percent chance of at
least one avalanche impact in 50 years" is a fair summary. Blue zone implies
people inside a solid building are largely safe; the exposure is structural
damage (uphill face, openings) and anyone outdoors. Expect occasional
evacuations in extreme winters — Zinal was evacuated in January 2018 and runs
automated avalanche control plus an avalanche radar on the Garde de Bordon.
Climate trend to ~2076 at 1700 m (SLF): fewer dry-snow avalanches, more wet-snow
avalanches, with a clear decrease only late-century — the hazard shrinks but
does not disappear within 50 years.

**Debris flow is the risk to watch.** Activity is projected to increase (more
intense precipitation, permafrost degradation in the catchments), and a future
map revision can move a corridor boundary. Access roads and gardens are usually
exposed before the buildings are.

**Earthquake is the sneaky one.** Zone Z3b plus a roughly once-per-century M≈6
event in Valais gives on the order of a 40 % chance of a strong regional quake
in 50 years. Light timber structures behave well (light, ductile); what matters
is anchoring of frame-to-foundation and of the stove and chimney.

## Practical implications

- Renovation or extension in a blue zone triggers **blue-zone conditions**
  (SDANA / commune): reinforced uphill façade, limits on openings facing the
  slope. Consult the communal *plan des zones de danger* before works.
- Avalanche and debris-flow damage is covered as *dommages naturels* under the
  mandatory elemental-damage part of a Swiss fire policy — confirm rebuild value.
- Winter occupancy coincides with avalanche season; subscribe to the commune's
  alert channel.

## Sources

- Canton VS hazard maps via [geodienste.ch](https://www.geodienste.ch/services/gefahrenkarten?locale=fr)
  (WMS `https://geodienste.ch/db/gefahrenkarten_v1_3_0/deu`) — check visually on
  [map.geo.vs.ch](https://map.geo.vs.ch/) (theme "Dangers naturels")
- [Federal viewer map.geo.admin.ch](https://map.geo.admin.ch/) (SilvaProtect,
  Aquaprotect, runoff, permafrost, hail, SIA 261, historical quakes)
- [VS RDPPF extract service](https://www.cadastre.ch/fr/service-web-rdppf)
- [VS cartes de danger (SDANA)](https://www.vs.ch/web/sdana/cartes-de-danger)
- SLF: [climate change & avalanches](https://www.slf.ch/en/news/climate-change-and-avalanches/),
  [climate change & alpine hazards](https://www.slf.ch/en/news/climate-change-leads-to-more-alpine-hazards/),
  [WSL — 25 years since winter 1999](https://www.wsl.ch/en/news/25-years-since-the-avalanche-winter-of-1999/)
- [Zinal avalanche & people radar (GEOPRÆVENT)](https://www.geopraevent.ch/project/avalanche-and-people-radar-zinal/?lang=en)
- [UNIGE — Zinal, natural history](https://www.unige.ch/forel/en/services/guide/zinal-histoire-naturelle-et-presence-humaine)
