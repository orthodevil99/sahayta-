# Sahayta Simulation Package (Wave 3, Agent 9)

Deterministic disaster-scenario generation, backend load simulation, and the
one-click demo director. All synthetic, stdlib only (no third-party deps).

## Layout

```
packages/simulation/
  sim_common.py        # repo paths, stdlib HTTP client, BackendBoot (seed+uvicorn)
  scenario_gen.py      # 2,000 deterministic scenarios (flood/heatwave/cyclone x 20 districts)
  scenarios/
    index.json         # compact index of all 2,000 (id, hazard, district, seed, peak, sos_count)
    sample/            # 50 materialized full scenarios
  load_sim.py          # replays scenarios vs the real backend; reports throughput/p95/triage
  load_results.json    # measured results from the last run
  demo_director.py     # 14-step patna-flood replay; exit 0 iff all PASS
  SIMULATION_REPORT.md # the numbers (scenarios, load, director)
  NOTES-agent9.md      # design decisions
  tests/               # pytest: generator determinism + director behavior
```

## Quickstart

```bash
cd packages/simulation

# regenerate the 2,000-scenario index + 50 samples
python3 scenario_gen.py --all

# one-click demo acceptance replay (fresh seed + boot + 14 checks)
python3 demo_director.py --scenario patna-flood

# load test vs a fresh backend (30 scenarios x 6 SOS + reads)
python3 load_sim.py --scenarios 30 --sos-per-scenario 6

# unit tests
python3 -m pytest tests/ -q
```

`demo_director.py` and `load_sim.py` boot their own backend (fresh
`seed.py --fresh` + uvicorn) on ports 8003 / 8002 by default — override with
`--port`, or drive an existing server with `--no-boot --base-url ...`.

## Results (measured 2026-10-06)

- Scenarios: 2,000 indexed, 271,513 synthetic SOS events.
- Load: 275 requests, 0 errors, 16.8 req/s, p95 107.0 ms.
- Demo director: **14/14 PASS, exit 0.**
- Tests: 12/12 pass.

See `SIMULATION_REPORT.md` for the full honest numbers.
