# GTA VI Trophy Rarity Forecast

Python 3.13 entry for the make.fun bounty "Forecast how many GTA VI players earn each trophy in week one".

The program reads every case in `/input`, forecasts five quantiles of each PS5 trophy's Exophase earn rate at the case's target, and writes one JSON file per case to `/output`. The model combines the case's latest history with a public Exophase observation, then extrapolates on the logit scale with tier-aware drift and quantile spread.

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/0xRzbal/trophy-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/0xRzbal/trophy-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Bounty: https://make.fun/bounty/gta6-trophy-rarity-forecast-01

## Run

```
python3 main.py
```

With local case files:

```
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

MIT
