# Testing

This document covers how the app is tested: which assessment requirement each test proves, what runs automatically on every push, and a manual checklist for the live deployment, where real routing and weather data can't be stubbed.

## 1. Requirement → proof

| # | Assessment requirement | Where it lives | Automated proof | Live check (§3) |
|---|---|---|---|---|
| R1 | User enters origin, destination, departure date/time, and load weight | `TripForm.jsx`, `TripPlanSerializer` | API validation tests; e2e: validation, autocomplete | L1, L9 |
| R2 | 3 route options from a routing API | `providers/tomtom.py`, `services.fetch_routes` | adapter tests (truck mode, weight in kg); API test: via-point fallback still gives 3 routes | L2, L3 |
| R3 | Weather every 10 / 25 / 50 miles | `domain/sampling.py` | spacing test per interval; API test: interval controls checkpoint count | L4 |
| R4 | …using the truck's ETA at each checkpoint | `sampling.time_curve`, `HourlySeries.at` | ETA follows the router's timing, not average speed; ETAs always increase; interpolation between forecast hours | L5 |
| R5 | Risk from the wind, rain and snow table | `domain/risk.py` | every threshold boundary for all three conditions | L6 |
| R6 | Load rules (≥55 any load; 45–54 and >30k; 35–44 and >40k) | `domain/risk.LOAD_RULES` | every load-rule edge; API test: heavier load turns Severe into No Travel | L7 |
| R7 | Recommend: fewest Severe miles → High miles → average risk → time | `domain/recommend.py` | one test per tie-break step; No Travel ranks worst; "no safe route" flag | L8 |
| R8 | Show routes, checkpoints, risk levels, ETAs and summaries on a map | `MapView.jsx`, `RouteCard`, `CheckpointList` | e2e: 3 cards, one recommended, checkpoint table, popup | L10 |
| R9 | Weather heatmap along the corridor with a 0–48 h slider | `services.build_heatmap`, `HeatmapControls`, `lib/heatmap.js` | API test: 49 frames × N cells; e2e: slider, play, metric toggle | L11, L12 |
| Q1 | Map and heatmap smoothness and performance | feature-state recolouring, one heatmap fetch per trip | no network calls while scrubbing; query-count guard (3 queries per trip) | L12, L13 |
| Q2 | Code quality | ruff, ESLint, Prettier, CI | CI gates every push | – |

## 2. Automated tests (run on every push in GitHub Actions)

| Layer | Command | What it covers |
|---|---|---|
| Backend unit + API | `cd backend && pytest --cov` | 109 tests, about 97% coverage. Domain rules, adapters (HTTP mocked with `respx`), API, auth, permissions, error format, query counts. |
| Frontend unit | `cd frontend && npm test` | Polyline decoding, route splitting, truck position, heatmap expressions, route card, error messages. |
| End-to-end | `cd frontend && npm run e2e` | A real browser against the real Django API, with fake route and weather providers (`backend/tests/fakes.py`). Covers planning, the unsafe-trip banner, route switching, popups, heatmap play and toggle, reloading a trip link, validation, autocomplete, and sign up → history → delete → sign out. Also a smoke run at phone size. |
| Static checks | `ruff`, `eslint`, `prettier --check`, `makemigrations --check` | Style, likely bugs, and missing migrations. |

The fake providers put a 50 mph wind storm north of latitude 41.4°. That makes the results deterministic: Dallas → Atlanta is calm, and Chicago → Minneapolis is No Travel at a 36,000 lb load.

## 3. Live checklist (deployed app, real TomTom and Open-Meteo)

Open the API health check first, because the free server takes about a minute to wake up. Time each plan request; a long trip should still finish in a few seconds once the server is awake.

| # | Scenario | Steps | Expected |
|---|---|---|---|
| L1 | Happy path | Denver → Salt Lake City, departure 2 hours from now, 36,000 lb, 25 mi | 3 routes, one recommended with a reason, checkpoints every 25 mi, heatmap appears |
| L2 | Short trip (fallback routes) | Dallas → Fort Worth | Still 3 routes, or fewer if no sensible detour exists; never 3 copies of the same route |
| L3 | Long trip | Seattle → Miami | Completes; checkpoints and heatmap still load; slider stays smooth |
| L4 | Intervals | Plan the same trip at 10, 25 and 50 mi | Checkpoint count goes down by roughly 2.5× and then 2× |
| L5 | ETA sanity | Look at the first and last checkpoint ETAs | First = departure; last ≈ departure + route duration |
| L6 | Weather truth | Pick one checkpoint, then check open-meteo.com or weather.gov at that place and hour | Wind, rain and snow match to within rounding |
| L7 | Load sensitivity | Find a windy day (wind ≥ 35 mph). Plan at 20,000 lb, then at 45,000 lb | The heavier load raises High to Severe (35–44 mph) or Severe to No Travel (45–54 mph) |
| L8 | Recommendation logic | Read the explanation and compare the route cards | The ranking matches Severe → High → average risk → time |
| L9 | Bad input | Same origin and destination; departure in the past; departure 8 days out; load 0 | A clear inline or API error, and no crash |
| L10 | Map interactions | Hover cards, click a route on the map, click checkpoints, zoom | The highlight follows; popups show ETA, values and reasons |
| L11 | Heatmap | Drag the slider 0 → 48, press play, switch Risk/Wind/Rain/Snow | Colours change smoothly; the time label and truck marker move |
| L12 | Performance | Chrome DevTools → Network while scrubbing; Performance → record scrubbing | **No** network requests during scrubbing; frames stay close to 60 fps |
| L13 | Cold start | Wait 20 minutes, then plan a trip | The first request is slow (Render free tier) but succeeds; later ones are fast |
| L14 | Unroutable | Honolulu → Denver | A friendly "No truck route found" error |
| L15 | Search | Type gibberish; type a ZIP code; type a street address | "No places found"; ZIP and address resolve |
| L16 | Auth | Sign up, plan, reload, sign out, sign in, check history; open your trip link in a private window | History persists. The signed-in trip is private (404 when signed out); anonymous trip links are shareable |
| L17 | Session expiry | Stay signed in for more than 30 minutes, then plan | Still works: the token refreshes silently |
| L18 | Rate limit | Plan more than 30 trips in an hour | A clear "too many requests" message |
| L18b | Weather quota | Plan Anchorage → Montreal at 10 mi, then plan two more long trips within the same minute | The first succeeds (with a coarser weather lattice). A later one may show "try again in about a minute"; it should never show a raw Open-Meteo error |
| L19 | Devices | Phone (portrait), tablet, Chrome, Firefox, Safari | Layout fits; the map and controls are usable |

## 4. Known limitations

- The free Open-Meteo tier allows about 600 locations a minute and 10,000 a day. Very long trips use a coarser weather lattice, cached locations are free, and a paid key (`OPEN_METEO_API_KEY`) removes the limits.

- The heatmap covers 48 hours from departure. On a trip longer than that, checkpoints still get their own ETA forecasts, but the slider stops at +48 h.
- Forecasts are limited to 7 days ahead, and departures are checked against that.
- Routing comes from TomTom's truck profile. Bridge heights and hazmat restrictions would need the vehicle's dimensions, which the brief doesn't ask for.
