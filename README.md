# GTA VI Trophy Rarity Forecast

Python 3.13 entry for the make.fun bounty "Forecast how many GTA VI players earn each trophy in week one".

This tool processes every case found in `/input`, producing five quantile forecasts for each PS5 trophy's Exophase earn rate at the case's target date. Results are written as one JSON file per case to `/output`. The forecast blends the case's most recent history with a public Exophase observation and extrapolates on the logit scale using tier-aware drift and quantile spread.

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/0xRzbal/trophy-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/0xRzbal/trophy-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Bounty: https://make.fun/bounty/gta6-trophy-rarity-forecast-01

## Running

Run a default forecast with:

```
python3 main.py
```

To use local case files instead:

```
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

MIT
