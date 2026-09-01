from dataclasses import replace
from .config import Config, StrategyParams
from .core import Indicators, SignalEngine, RiskGuardian, State, PaperExecutor
import pandas as pd, numpy as np

class Metrics:
    @staticmethod
    def summary(equity_curve, trades):
        e=np.asarray(equity_curve,dtype=float)
        if len(e)<2:return {"trades":len(trades),"max_drawdown":0.0,"sharpe":0.0,"sortino":0.0,"profit_factor":0.0}
        rets=pd.Series(e).pct_change().dropna(); peak=pd.Series(e).cummax(); dd=(pd.Series(e)/peak-1).min()
        sharpe=float(rets.mean()/rets.std()*np.sqrt(96*252)) if rets.std()>0 else 0.0
        downside=rets[rets<0].std(); sortino=float(rets.mean()/downside*np.sqrt(96*252)) if downside and downside>0 else 0.0
        wins=sum(max(0,t) for t in trades); losses=sum(-min(0,t) for t in trades)
        return {"trades":len(trades),"max_drawdown":float(-dd),"sharpe":sharpe,"sortino":sortino,"profit_factor":float(wins/losses) if losses else float("inf")}

class AdaptiveController:
    def __init__(self,cfg:Config): self.cfg=cfg
    def candidates(self,base:StrategyParams):
        out=[base]
        for name,lo,hi,step in self.cfg.allowed_param_ranges:
            v=getattr(base,name); nv=v+step
            if nv<=hi: out.append(replace(base,**{name:nv}))
            nv=v-step
            if nv>=lo: out.append(replace(base,**{name:nv}))
        return out
    def score(self,df,p):
        if len(df)<150:return (-1e9,{})
        split=int(len(df)*0.6); val_start=split; val_end=int(len(df)*0.8); test_start=val_end
        result=[]
        for a,b in [(0,split),(val_start,val_end),(test_start,len(df))]: result.append(self._run(df.iloc[a:b].copy(),p))
        train,val,test=result
        # Conservative acceptance: validation must improve and test must remain above a hard quality floor.
        score=0.25*train["net"]+0.5*val["net"]+0.25*test["net"]
        ok=val["net"]>0 and test["max_dd"]<self.cfg.limits.hard_drawdown and test["trades"]>=10
        return (score if ok else -1e9,{"train":train,"validation":val,"test":test})
    def _run(self,df,p):
        df=Indicators.add(df,p); equity=self.cfg.initial_equity; peak=equity; maxdd=0; trades=[]; pos=None
        for i in range(1,len(df)):
            r=df.iloc[i]; prev=df.iloc[i-1]
            if pos:
                stop=(pos["side"]==1 and r.l<=pos["stop"]) or (pos["side"]==-1 and r.h>=pos["stop"])
                target=(pos["side"]==1 and r.h>=pos["target"]) or (pos["side"]==-1 and r.l<=pos["target"])
                if stop or target:
                    px=pos["stop"] if stop else pos["target"]; pnl=(px-pos["entry"])*pos["size"]*pos["side"]
                    equity+=pnl; trades.append(pnl); pos=None
            if not pos:
                s=SignalEngine.signal(prev,r,p)
                if s:
                    stop=r.c-s*p.sl_atr*r.atr; size=equity*self.cfg.limits.risk_per_trade/abs(r.c-stop); size=min(size,equity*self.cfg.limits.max_notional_leverage/r.c)
                    if size>0:pos={"side":s,"entry":r.c,"size":size,"stop":stop,"target":r.c+s*p.tp_atr*r.atr}
            peak=max(peak,equity); maxdd=max(maxdd,1-equity/peak)
        return {"net":equity/self.cfg.initial_equity-1,"max_dd":maxdd,"trades":len(trades)}
    def propose(self,df,current):
        best=(-1e9,current,None)
        for p in self.candidates(current):
            score,detail=self.score(df,p)
            if score>best[0]:best=(score,p,detail)
        return best
