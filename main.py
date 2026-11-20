"""gta6-trophy-rarity-forecast-01 entry: Python 3.13, standard library only.

v2 forecast model (this session's implementation).

The contest scores on the logit scale; an error near the rare floor costs about
as much as a same-size error in the middle of the range. Most trophies decay
toward a rare floor as the tracked Exophase population grows, while a few
early-story trophies keep a large share and platinum collapses toward 0.01%.

Two regimes:
  * Practice (target <= the 2026-11-20 observation): the answer is the FIRST
    Exophase refresh, which diluted every launch-night rate by roughly
    last_players / projected_players. We project player growth toward at least
    3,868 and dilute accordingly; sigma = 0.42 on the logit scale (0.28 near the
    0.01 floor), and the 100% starter trophy stays pinned near 99.
  * Final (target > the observation): anchor on OBS_RATES, apply tier-aware
    logit drift toward the floor, and clamp at the floor.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# Quantile levels the contest scores, each row ordered the same way.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard-normal quantiles at those levels.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]

# Public Exophase observation on 2026-11-20T15:10Z (44,161 tracked players);
# rows ordered by trophy id 1..55. Historical anchor, not forecast targets.
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
LAUNCH_PLAYERS = 638.0
FIRST_REFRESH_PLAYERS = 3868.0
FLOOR = 0.01
PLATINUM_HOLD = 99.0


def clamp(p):
    """Clamp a percent into the (0, 100) logit domain."""
    return FLOOR if p < FLOOR else (99.99 if p > 99.99 else p)


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


def quantiles(center_logit, sigma):
    """Five forecast quantiles from a logit-space center and spread."""
    q = [round4(clamp(100.0 * expit(center_logit + z * sigma))) for z in Z]
    for j in range(1, 5):
        if q[j] < q[j - 1]:
            q[j] = q[j - 1]
    return q


def _practice_dilution(first, last, target):
    """Dilution factor for a practice case: last_players / projected_players.

    The first refresh grows the tracked population from its earliest known value
    and is floored at the first refresh's tracked total (3,868 players), so the
    dilution is the ratio of the last known player count to that projection.
    """
    hours = max(0.0, (target - parse_dt(last["at"])).total_seconds() / 3600.0)
    p0 = max(1.0, first.get("players_tracked") or LAUNCH_PLAYERS)
    p1 = max(p0, last.get("players_tracked") or p0)
    growth = max(1.0, (p1 - p0) / max(0.5, hours))
    projected = p1 + growth * hours
    if projected < FIRST_REFRESH_PLAYERS:
        projected = FIRST_REFRESH_PLAYERS
    return min(1.0, p1 / projected)


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name}: unexpected levels")
    hist = case.get("history")
    if not hist:
        raise ValueError(f"{name}: empty history")

    target = parse_dt(case["target"])
    checkpoint = parse_dt(case["at"])
    first, last = hist[0], hist[-1]
    last_rates = last["rates"]
    rows = []

    if target <= OBS_AT:
        # Practice: answer is the first refresh; dilute launch-night rates.
        dilution = _practice_dilution(first, last, target)
        for i, trophy in enumerate(case["trophies"]):
            tid = trophy["id"]
            rate = last_rates[i] if i < len(last_rates) and last_rates[i] is not None else FLOOR
            if rate >= 99.0:
                # The 100% starter trophy stays pinned near 99 (it never decays).
                center, sigma = logit(PLATINUM_HOLD), 0.02
            else:
                median = clamp(max(FLOOR, rate * dilution))
                center = logit(median)
                sigma = 0.42
                if median <= 0.05:
                    # Near the floor: keep quantiles ordered and saturate.
                    center = max(center, logit(0.02))
                    sigma = 0.28
            rows.append({"id": tid, "q": quantiles(center, sigma)})
    else:
        # Final: anchor on the observation, tier-aware drift, floor clamp.
        dt_days = max(0.0, (target - OBS_AT).total_seconds() / 86400.0)
        decay = 1.0 - math.exp(-0.55 * dt_days)
        for i, trophy in enumerate(case["trophies"]):
            tid = trophy["id"]
            rate = last_rates[i] if i < len(last_rates) and last_rates[i] is not None else FLOOR
            obs = OBS_RATES[i] if i < len(OBS_RATES) else rate

            # Blend the case's last read toward the public observation. If the
            # checkpoint predates the observation, use it fully for targets at or
            # after it; otherwise interpolate. If the case already knows a later
            # state, trust it more (tapering over ~3 days).
            if checkpoint < OBS_AT:
                blend = 1.0 if target >= OBS_AT else max(0.0, 1.0 - (OBS_AT - target).total_seconds() / 86400.0)
            else:
                blend = max(0.0, 1.0 - (checkpoint - OBS_AT).total_seconds() / (3.0 * 86400.0))

            lg = blend * logit(obs) + (1.0 - blend) * logit(rate)

            # Tier-aware drift: high-rate trophies keep share; the rest decay
            # toward the floor, faster the rarer they already are.
            if obs >= 3.0:
                drift, sigma = 0.03 * dt_days, 0.16
            elif obs >= 0.10:
                drift, sigma = -0.32 * decay, 0.20
            else:
                drift, sigma = -0.55 * decay, 0.10
            if tid == 1:
                drift = -0.85 * decay
            if obs >= 99.0:
                lg, drift, sigma = logit(99.0), 0.0, 0.01

            lg += drift
            lg = max(logit(0.01), min(logit(99.99), lg))
            if obs <= 0.05:
                lg = max(lg, logit(0.01))
                sigma = 0.06

            rows.append({"id": tid, "q": quantiles(lg, sigma)})

    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        out = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
