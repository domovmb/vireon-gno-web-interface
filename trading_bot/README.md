# EURUSD Survival Bot

Single-process, survival-first Hyperliquid HIP-3 paper bot for `xyz:EURUSD`.

## Pipeline

`MarketData -> Context -> Indicators -> Regime -> Signal -> RiskGuardian -> Execution -> Journal -> Metrics -> AdaptiveController`

Risk rules are immutable at runtime: 0.5% risk/trade, 2x max notional leverage, -3% daily stop, -20% hard kill from equity peak. Adaptive learning can only change strategy parameters inside an allowlisted bounded space and only after walk-forward validation.

Paper-only by default. There is deliberately no live order path in this version.

## Run

```bash
python -m trading_bot.main --mode backtest
python -m trading_bot.main --mode paper
```

The paper loop uses Hyperliquid public Info/WebSocket data. The exchange is queried with the HIP-3 coin name `xyz:EURUSD`.
