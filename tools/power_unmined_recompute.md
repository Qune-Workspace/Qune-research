# Separate-session recomputation of `tools/power_unmined.txt`

Reviewer: a separate Opus 5.5 session, 2026-10-26 05:2xZ, read-only, told not to open `tools/power_unmined.py`, given the definitions only (brief: recompute every printed figure and the derived numbers in the 05:2xZ RESEARCH_AGENDA addition). Run time about 99 s. The report below is verbatim except that absolute local paths were replaced by `./` and three HTML-escaped characters in the script (`>=`, `&`, `<=`) were restored.

**Response (author).** Both should-fix were taken before the agenda text was committed: the break-even correlation is now stated as about 0.7 (0.71), and the leg bias is set against the rules' own Sharpe(d) over the same months (23% to 33%), with the full-window share (13% to 25%) beside it. The first note (U's switch forms against Study 006's own Sharpe) was added to the agenda text. The other notes stand as written: they make the calculation slightly conservative for the country pool and do not change the decision.

---

# Recomputation of tools/power_unmined.txt

I recomputed everything from the three `monthly_base.csv` files with my own script, which is under ./recompute_unmined/ and appended below. I did not read tools/power_unmined.py. **Every printed number matches at its printed precision, and every derived number in the 05:2xZ agenda addition holds.** One agenda sentence understates its own case, and the 40% to 87% figure mixes two denominators (concerns below). The three bias strings (+0.626%, +0.570%, +0.766%) do exist in tools/fidelity_stocker.txt, lines 6–8.

| Row (published → mine) | Match |
|---|---|
| 006: n 593, 1969-08 to 2018-12, t 2.06, +0.90%, sd 3.20%, Sh 0.282, nw 0.963, 1129 (1128.76) | yes, all |
| 007: 534, 1974-07 to 2018-12, 2.10, +0.85%, 2.73%, 0.309, 0.981, 976 (976.28) | yes, all |
| 008: 534, 1974-07 to 2018-12, 1.38, +0.56%, 2.49%, 0.227, 1.095, 2261 (2260.58) | yes, all |
| pool: 534, 1974-07 to 2018-12, 2.17, +0.70%, 2.19%, 0.321, 0.989, 917 (916.64) | yes, all |
| corr 006-007 0.719, 006-008 0.314, 007-008 0.193 | yes |
| U switch, daily inputs: N 90, MDE 1.026, 3.2x (3.19) | yes |
| U switch, monthly inputs: 195, 0.697, 2.2x (2.17) | yes |
| U tilts: 136, 0.835, 2.6x (2.60) | yes |
| C months: GBR 742, DEU 742, CAN 790, FRA 622, AUS 628, total 3524 | yes |
| C rho 0.25: N_eff 1762, MDE 0.232, 0.7x (0.72) | yes |
| C rho 0.50: 1175 (1174.67), 0.284, 0.9x (0.88) | yes |
| C rho 0.75: 881, 0.328, 1.0x (1.02) | yes |
| Bias 006: sd 5.58% (n 159), +0.112; whole-history sd 3.20%, +0.195; Sh 0.282 | yes |
| Bias 007: sd 4.44% (n 100), +0.128; whole-history sd 2.73%, +0.209; Sh 0.309 | yes |
| Bias 008: sd 3.89% (n 100), +0.197; whole-history sd 2.49%, +0.308; Sh 0.227 | yes |

**Agenda's derived claims**
- Arithmetically correct: "Sharpe(d) 0.321 (+0.70% a year over 534 months, t 2.17)", "about 917 months", "1.03 / 0.70 / 0.84", "0.23 / 0.28 / 0.33", "3,524", "2.2× to 3.2×" (2.17–3.19), "0.7× to 1.0×" (0.72–1.02), "+0.11, +0.13 and +0.20", "40% to 87%" (39.7%–86.7%) and "0.282, 0.309, 0.227".
- "Just enough only if the correlation is about 0.5 or lower" is true but too strict. With these formulas the break-even is where N_eff equals 916.64 months, which is rho = 0.711. Rho 0.75 just misses; anything up to about 0.71 is enough.
- "More than twice the size": the best U form is 2.17x, so this holds.
- "OECD yields on FRED from 1956–1970" matches the start months I was given. I could not check FRED itself (no internet).

**Methodological concerns**
- **should-fix**: "40% to 87%" divides a bias scaled by the 1969/74–1982 standard deviation by a Sharpe(d) taken over the whole history. On a consistent footing the figure changes a lot:
  - same-subperiod Sharpe(d) (0.486, 0.470, 0.592): 23% to 33%;
  - whole-history sd (0.195, 0.209, 0.308 against 0.282, 0.309, 0.227): 68% to 136%;
  - bias spread over the full window (the fidelity file's +0.168%, +0.107%, +0.143%): about 13% to 25%.

  The agenda should say which footing it uses. The conclusion ("not checkable abroad") does not depend on it.
- **should-fix**: the "rho about 0.5 or lower" sentence. Restate it as about 0.7 or lower, or explain why it is stricter.
- **note**: U's "switch" forms test only the 006 rule, yet they are compared with the pool's Sharpe 0.321 and use the pool's nw ratio. Against 006's own 0.282 the ratios become 3.6x and 2.5x. This makes the "U cannot see the edge" conclusion stronger, not weaker.
- **note**: N_eff = total/(1+4·rho) assumes all five countries overlap in every month. FRA and AUS start about 10 years later, so the true N_eff is a little higher and the C MDEs are slightly conservative. The pool's nw ratio (0.989) is also carried over to the foreign d without evidence.
- **note**: months to see = n(K/t)² is exactly 12(K·nw/Sh)², so the 917 figure and the MDE column use the same formula. K = 2.0 + 0.842 means a two-sided 5% test with 80% power.

**Script** (./recompute_unmined/recompute.py, run with the repo venv's python -I)
```python
import numpy as np, pandas as pd, statsmodels.api as sm
R = "./research/"
S = {"006": ("006-term-spread-switch-long-history", "B3"),
     "007": ("007-bond-carry-tilt-long-history", "B3_T1"),
     "008": ("008-bond-value-tilt-long-history", "B3_T1")}
K = 2.842
def load(k):
    p, b = S[k]; df = pd.read_csv(R + p + "/results/history/monthly_base.csv")
    d = (df["T1"] - df[b]); d.index = df["execution_date"].str[:7]; return d.dropna()
def stats(d):
    n = len(d); y = d.values
    se = sm.OLS(y, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": 6}).bse[0]
    sd = y.std(ddof=1); m = y.mean()
    return dict(n=n, w=f"{d.index[0]} to {d.index[-1]}", t=m/se, mean=m*12*100, sd=sd*np.sqrt(12)*100,
                sh=m/sd*np.sqrt(12), ratio=se/(sd/np.sqrt(n)), see=n*(K/(m/se))**2)
D = {k: load(k) for k in S}
D["pool"] = pd.concat([D[k] for k in S], axis=1, join="inner").mean(axis=1)
st = {}
for k, d in D.items():
    s = st[k] = stats(d)
    print(f"{k} {s['n']} {s['w']} t={s['t']:.2f} mean={s['mean']:+.2f}% sd={s['sd']:.2f}% "
          f"Sh={s['sh']:.3f} ratio={s['ratio']:.3f} see={s['see']:.2f}")
c = pd.concat([D[k] for k in S], axis=1, join="inner").corr()
print("corr %.3f %.3f %.3f" % (c.iloc[0,1], c.iloc[0,2], c.iloc[1,2]))
nw, shp = st["pool"]["ratio"], st["pool"]["sh"]
mde = lambda N: K*nw/np.sqrt(N/12)
def nm(a, b):
    ya, ma = map(int, a.split("-")); yb, mb = map(int, b.split("-")); return (yb-ya)*12+(mb-ma)+1
N2 = nm("1953-04", "1969-06")
for N in (nm("1962-01", "1969-06"), N2, N2-60+1): print(f"US N={N} MDE={mde(N):.3f} x={mde(N)/shp:.2f}")
cty = {"GBR": "1960-01", "DEU": "1960-01", "CAN": "1956-01", "FRA": "1970-01", "AUS": "1969-07"}
cn = {k: nm(v, "2026-09")-60+1 for k, v in cty.items()}; tot = sum(cn.values()); print(cn, tot)
for rho in (0.25, 0.5, 0.75):
    ne = tot/(1+4*rho); print(f"rho {rho} Neff={ne:.2f} MDE={mde(ne):.3f} x={mde(ne)/shp:.2f}")
print("rho* %.3f" % ((tot/st["pool"]["see"]-1)/4))
for k, (b, a) in {"006": (0.626, "1969-08"), "007": (0.570, "1974-07"), "008": (0.766, "1974-07")}.items():
    d = D[k]; sub = d[(d.index >= a) & (d.index <= "1982-10")]; sds = sub.std(ddof=1)*np.sqrt(12)*100
    print(f"{k} n={len(sub)} sd_sub={sds:.2f}% bias={b/sds:.3f} whole={b/st[k]['sd']:.3f} "
          f"share={b/sds/st[k]['sh']:.1%} subSh={sub.mean()/sub.std(ddof=1)*np.sqrt(12):.3f}")
```
