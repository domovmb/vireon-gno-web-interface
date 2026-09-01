from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
import math
import requests
import pandas as pd
from .config import Config, StrategyParams

INFO_URL = "https://api.hyperliquid.xyz/info"

@dataclass
class Position:
    side: int
    entry: float
    size: float
    stop: float
    target: float
    opened_at: int

@dataclass
class State:
    equity: float
    peak_equity: float
    day_start_equity: float
    day_key: str
    position: Optional[Position] = None
    realized_pnl: float = 0.0
    consecutive_losses: int = 0
    cooldown_until: int = 0
    killed: bool = False

class MarketData:
    def __init__(self, cfg: Config): self.cfg = cfg
    def candles(self, start_ms: int, end_ms: int) -> pd.DataFrame:
        r = requests.post(INFO_URL, json={"type":"candleSnapshot","req":{"coin":self.cfg.coin,"interval":self.cfg.interval,"startTime":start_ms,"endTime":end_ms}}, timeout=20)
        r.raise_for_status()
        rows = r.json()
        df = pd.DataFrame(rows)
        if df.empty: return df
        for c in ["o","h","l","c","v"]: df[c] = pd.to_numeric(df[c])
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        return df.sort_values("t").drop_duplicates("t").reset_index(drop=True)
    def context(self) -> dict:
        r = requests.post(INFO_URL, json={"type":"metaAndAssetCtxs","dex":"xyz"}, timeout=20)
        r.raise_for_status(); meta, ctxs = r.json()
        for i, item in enumerate(meta.get("universe", [])):
            if item.get("name") == "EURUSD":
                return {**item, **ctxs[i]}
        raise RuntimeError("EURUSD not found in xyz HIP-3 metadata")

class Indicators:
    @staticmethod
    def add(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
        x=df.copy(); x["ema_fast"]=x.c.ewm(span=p.ema_fast,adjust=False).mean(); x["ema_slow"]=x.c.ewm(span=p.ema_slow,adjust=False).mean()
        delta=x.c.diff(); gain=delta.clip(lower=0).ewm(alpha=1/p.rsi_period,adjust=False).mean(); loss=(-delta.clip(upper=0)).ewm(alpha=1/p.rsi_period,adjust=False).mean(); rs=gain/loss.replace(0,math.nan); x["rsi"]=100-(100/(1+rs))
        tr=pd.concat([x.h-x.l,(x.h-x.c.shift()).abs(),(x.l-x.c.shift()).abs()],axis=1).max(axis=1); x["atr"]=tr.ewm(alpha=1/p.atr_period,adjust=False).mean()
        return x

class Regime:
    @staticmethod
    def allowed(row) -> bool:
        if row.atr <= 0 or row.c <= 0: return False
        atr_pct=row.atr/row.c
        return 0.00005 <= atr_pct <= 0.01

class SignalEngine:
    @staticmethod
    def signal(prev, row, p: StrategyParams) -> int:
        if not Regime.allowed(row): return 0
        up=row.ema_fast>row.ema_slow and prev.rsi <= p.rsi_trigger < row.rsi
        down=row.ema_fast<row.ema_slow and prev.rsi >= p.rsi_trigger > row.rsi
        return 1 if up else -1 if down else 0

class RiskGuardian:
    def __init__(self,cfg:Config,state:State): self.cfg=cfg; self.s=state
    def refresh_day(self, ts:int):
        key=datetime.fromtimestamp(ts/1000,timezone.utc).date().isoformat()
        if key!=self.s.day_key: self.s.day_key=key; self.s.day_start_equity=self.s.equity; self.s.consecutive_losses=0
    def allowed(self, ts:int) -> bool:
        self.refresh_day(ts)
        if self.s.killed or ts < self.s.cooldown_until: return False
        if self.s.equity <= self.s.peak_equity*(1-self.cfg.limits.hard_drawdown): self.s.killed=True; return False
        if self.s.equity <= self.s.day_start_equity*(1-self.cfg.limits.daily_loss_limit): return False
        return True
    def size(self, entry:float, stop:float) -> float:
        risk_cash=self.s.equity*self.cfg.limits.risk_per_trade
        distance=abs(entry-stop)
        if distance<=0:return 0
        size=risk_cash/distance
        return min(size, self.s.equity*self.cfg.limits.max_notional_leverage/entry)
    def closed(self,pnl:float,ts:int):
        self.s.equity += pnl; self.s.realized_pnl += pnl; self.s.peak_equity=max(self.s.peak_equity,self.s.equity)
        self.s.consecutive_losses = self.s.consecutive_losses+1 if pnl<0 else 0
        if self.s.consecutive_losses>=self.cfg.limits.cooldown_losses: self.s.cooldown_until=ts+self.cfg.limits.cooldown_minutes*60*1000
        if self.s.equity <= self.s.peak_equity*(1-self.cfg.limits.hard_drawdown): self.s.killed=True

class PaperExecutor:
    def __init__(self,cfg:Config,state:State): self.cfg=cfg; self.s=state
    def open(self,side:int,price:float,atr:float,ts:int,risk:RiskGuardian,p:StrategyParams):
        stop=price-side*p.sl_atr*atr; target=price+side*p.tp_atr*atr; size=risk.size(price,stop)
        if size<=0:return
        fill=price*(1+side*self.cfg.slippage_bps/10000); self.s.position=Position(side,fill,size,stop,target,ts)
    def mark(self,row,risk:RiskGuardian):
        p=self.s.position
        if not p:return
        hit=(p.side==1 and (row.l<=p.stop or row.h>=p.target)) or (p.side==-1 and (row.h>=p.stop or row.l<=p.target))
        if not hit:return
        # Conservative: if both stop and target occur in one candle, stop wins.
        stop_hit=(p.side==1 and row.l<=p.stop) or (p.side==-1 and row.h>=p.stop)
        exit_px=p.stop if stop_hit else p.target
        pnl=(exit_px-p.entry)*p.size*p.side
        pnl-=abs(p.entry*p.size)*self.cfg.fee_rate; pnl-=abs(exit_px*p.size)*self.cfg.fee_rate
        risk.closed(pnl,int(row.t.value//10**6)); self.s.position=None

class Journal:
    def __init__(self,path="trading_bot/trades.csv"): self.path=path
    def append(self,record):
        import csv, os
        exists=os.path.exists(self.path); os.makedirs(os.path.dirname(self.path),exist_ok=True)
        with open(self.path,"a",newline="") as f:
            w=csv.DictWriter(f,fieldnames=record.keys())
            if not exists:w.writeheader()
            w.writerow(record)
