from __future__ import annotations
import argparse, time
from datetime import datetime, timezone, timedelta
from .config import Config
from .core import MarketData, Indicators, SignalEngine, State, RiskGuardian, PaperExecutor, Journal
from .learning import AdaptiveController, Metrics

def run_backtest(cfg, days=30):
    md=MarketData(cfg); end=datetime.now(timezone.utc); start=end-timedelta(days=days)
    df=md.candles(int(start.timestamp()*1000),int(end.timestamp()*1000))
    if df.empty: raise RuntimeError("No candles returned")
    df=Indicators.add(df,cfg.params); state=State(cfg.initial_equity,cfg.initial_equity,cfg.initial_equity,"",None); risk=RiskGuardian(cfg,state); exe=PaperExecutor(cfg,state); eq=[state.equity]; trades=[]
    for i in range(1,len(df)):
        row,prev=df.iloc[i],df.iloc[i-1]; ts=int(row.t.value//10**6); risk.refresh_day(ts); exe.mark(row,risk)
        if state.position is None and risk.allowed(ts):
            s=SignalEngine.signal(prev,row,cfg.params)
            if s: exe.open(s,row.c,row.atr,ts,risk,cfg.params)
        eq.append(state.equity)
    m=Metrics.summary(eq,trades)
    print({"equity":state.equity,"killed":state.killed,**m})

def run_paper(cfg):
    md=MarketData(cfg); state=State(cfg.initial_equity,cfg.initial_equity,cfg.initial_equity,"",None); risk=RiskGuardian(cfg,state); exe=PaperExecutor(cfg,state); journal=Journal(); learner=AdaptiveController(cfg); params=cfg.params
    print(f"PAPER ONLY: {cfg.coin} / {cfg.interval} / equity=${state.equity:.2f}")
    while not state.killed:
        end=datetime.now(timezone.utc); start=end-timedelta(days=10); df=md.candles(int(start.timestamp()*1000),int(end.timestamp()*1000))
        if len(df)<100: time.sleep(30); continue
        # Learn only on completed historical windows; no risk parameters are mutable.
        score,p,detail=learner.propose(df,params)
        if score>-1e8: params=p
        x=Indicators.add(df,params); row=x.iloc[-2]; prev=x.iloc[-3]; ts=int(row.t.value//10**6); risk.refresh_day(ts); exe.mark(row,risk)
        if state.position is None and risk.allowed(ts):
            s=SignalEngine.signal(prev,row,params)
            if s: exe.open(s,row.c,row.atr,ts,risk,params); journal.append({"ts":ts,"event":"OPEN","side":s,"price":row.c,"equity":state.equity})
        print(f"{row.t} equity=${state.equity:.2f} peak=${state.peak_equity:.2f} DD={(1-state.equity/state.peak_equity):.2%} killed={state.killed}")
        time.sleep(60)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=["backtest","paper"],default="backtest"); ap.add_argument("--days",type=int,default=30); a=ap.parse_args(); cfg=Config()
    run_backtest(cfg,a.days) if a.mode=="backtest" else run_paper(cfg)

if __name__=="__main__": main()
