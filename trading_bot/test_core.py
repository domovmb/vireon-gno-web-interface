import pandas as pd
from .config import Config
from .core import State, RiskGuardian, Indicators
from .learning import AdaptiveController

def test_hard_kill_is_immutable():
    cfg=Config(); s=State(100,100,100,"2026-01-01"); r=RiskGuardian(cfg,s)
    s.equity=79.99
    assert r.allowed(1760000000000) is False
    assert s.killed is True

def test_risk_size_never_exceeds_two_x_notional():
    cfg=Config(); s=State(100,100,100,"2026-01-01"); r=RiskGuardian(cfg,s)
    size=r.size(1.10,1.09)
    assert size*1.10 <= 200.000001

def test_learning_is_bounded():
    cfg=Config(); learner=AdaptiveController(cfg)
    df=pd.DataFrame({"o":[1.1]*220,"h":[1.101]*220,"l":[1.099]*220,"c":[1.1]*220,"v":[1.0]*220})
    p=cfg.params
    for candidate in learner.candidates(p):
        assert 8 <= candidate.ema_fast <= 40
        assert 30 <= candidate.ema_slow <= 120
        assert 1 <= candidate.sl_atr <= 2.5
        assert 1.5 <= candidate.tp_atr <= 4
