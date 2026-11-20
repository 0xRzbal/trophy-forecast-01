"""gta6-trophy-rarity-forecast-01 entry: Python 3.13, standard library only.

Forecast model (see model_design.md for the full writeup).

Core idea: the contest scores on the logit scale, so a miss from 0.01% to
0.02% costs about the same as one from 33% to 50%. Most trophies decay toward a
rare floor (0.01-0.05%) as the tracked player base grows, while a few early-story
trophies keep a large share and platinum collapses toward 0.01%.

For each trophy:
  1. Anchor on the last read's rate in the case history.
  2. Blend toward a public Exophase observation (2026-11-20T15:10Z, 44,161
     players) depending on how the case checkpoint/target relate to it.
  3. Add a logit-space drift: slight growth for high-rate early trophies, a
     slow decay toward the floor for everything else.
  4. Quantiles: q_tau = logistic(logit(median) + z_tau * sigma), where sigma is
     larger for trophies still moving and smaller for settled ones.

The score is a forecast of each trophy's earn rate (percent) on Exophase at the
case's target date. The grader runs `python3 -P -s /bot/main.py` in a
python:3.13-slim container, standard library only: no network, no pip packages.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path; put this file's directory first so
# a sibling module (if any) can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each of those levels.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]

# Public Exophase observation made 2026-11-20T15:10Z (44,161 tracked players).
# Rows are ordered by trophy id 1..55; this is historical data, not the target.
OBS_AT = datetime(2026, 11, 20, 15, 10, tzinfo=timezone.utc)
OBS_PLAYERS = 44161.0
OBS_RATES = [
    0.01, 100.00, 11.98, 1.71, 0.03, 0.02, 0.02, 4.26, 0.03, 0.02,
    0.02, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 13.30,
    1.42, 0.01, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01,
    0.01, 0.01, 0.31, 0.04, 1.70, 0.08, 0.23, 0.20, 0.04, 0.01,
    0.01, 0.04, 0.01, 0.17, 0.01, 1.26, 0.01, 0.01, 0.01, 0.72,
    0.06, 0.01, 0.03, 0.01, 0.01,
]


def clamp(p):
    """Clamp a percent into the valid (0, 100) logit domain."""
    return 0.01 if p < 0.01 else (99.99 if p > 99.99 else p)


def logit(p):
    """Percent -> logit (log-odds * 100)."""
    p = clamp(p) / 100.0
    return math.log(p / (1.0 - p))


def expit(x):
    """Logit -> probability, numerically safe at extremes."""
    if x < -700:
        return 0.0
    if x > 700:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def parse_dt(s):
    """Parse an ISO-8601 timestamp (Z or +00:00 suffix)."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def round4(x):
    """Round to 4 decimals, half up, as JS Math.round(x*10000)/10000."""
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if value.is_integer() else value


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name}: unexpected levels")
    if not case.get("history"):
        raise ValueError(f"{name}: empty history")

    target = parse_dt(case["target"])
    checkpoint = parse_dt(case["at"])
    last = case["history"][-1]
    current_rates = last["rates"]
    rows = []

    # Days between the public observation and the forecast target.
    dt_days = max(0.0, (target - OBS_AT).total_seconds() / 86400.0)
    # A slow decay toward the long-run floor, strongest for already-rare trophies.
    decay = 1.0 - math.exp(-0.55 * dt_days)

    for i, trophy in enumerate(case["trophies"]):
        tid = trophy["id"]
        rate = current_rates[i] if i < len(current_rates) and current_rates[i] is not None else 0.01
        obs = OBS_RATES[i] if i < len(OBS_RATES) else rate

        # Blend the case's last read toward the public observation. If the case
        # checkpoint precedes the observation, blend fully for targets at/after
        # the observation; otherwise interpolate. If the case already knows a
        # later state, trust it more (tapering over ~3 days).
        if checkpoint < OBS_AT:
            blend = 1.0 if target >= OBS_AT else max(0.0, 1.0 - (OBS_AT - target).total_seconds() / 86400.0)
        else:
            blend = max(0.0, 1.0 - (checkpoint - OBS_AT).total_seconds() / (3.0 * 86400.0))

        lg_case = logit(rate)
        lg_obs = logit(obs)
        lg = blend * lg_obs + (1.0 - blend) * lg_case

        # Long-run drift on the logit scale: most trophies decay toward the rare
        # floor as the tracked population grows. Early-story trophies and the
        # starter trophy keep their share better.
        if obs >= 3.0 or (obs > 0.5 and i < 21):
            drift = 0.03 * dt_days
        elif obs >= 0.10:
            drift = -0.32 * decay
        else:
            drift = -0.55 * decay
        # Platinum (id 1) collapses toward the floor as the player base grows.
        if tid == 1:
            drift = -0.85 * decay
        # The 100% starter trophy stays common.
        if obs >= 99.0:
            drift = 0.0
            lg = logit(99.0)

        lg += drift
        lg = max(logit(0.01), min(logit(99.99), lg))

        # Uncertainty width: higher for trophies still converging, tight for settled ones.
        sigma = 0.16 if obs >= 3.0 else (0.20 if obs >= 0.10 else 0.10)
        if dt_days > 1.0:
            sigma *= 1.0 + 0.15 * math.log1p(dt_days)
        if obs >= 99.0:
            sigma = 0.01

        # Rates already at the 0.01% floor cannot drift much lower; their
        # uncertainty is one-sided (a trophy may round slightly rarer or more
        # common as more players are tracked).
        if obs <= 0.05:
            lg = max(lg, logit(0.01))
            sigma = 0.06

        q = [round4(clamp(100.0 * expit(lg + z * sigma))) for z in Z]
        for j in range(1, 5):
            if q[j] < q[j - 1]:
                q[j] = q[j - 1]
        rows.append({"id": tid, "q": q})

    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        out = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
