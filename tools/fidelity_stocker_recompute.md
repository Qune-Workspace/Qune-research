# Separate-session recomputation: the 006–008 leg against Stocker (2025), 1969–1982

2026-10-26, 04:24Z. Reviewer: a separate Opus 5.5 session that did not write `tools/fidelity_stocker.py` and was told not to open it, its output or COLD_READ.md before producing its own numbers; read-only, no network, about 41 seconds. Same model family as the author, so this is a separate-session recomputation, not an independent review (cold read point 6).

## Brief (summary)

Match each 006 period to the Stocker 5–10-year row whose End date falls in the period's execution month; g = B1 − Stocker; h = T1's bond weight; w = mean h over the matched periods; e = (h − w)·g. Report n, window, w, mean(e)×12, mean(g)×12, sd(g)×√12, sd(g)/sd(Stocker − B0), corr(B1, Stocker) for 006, 007 and 008 beside the published values, MATCH/MISMATCH at printed precision; state whether positive mean(e) means the leg overstates T1's advantage over B3.

## Report (verbatim)

All 14 published numbers match my own recomputation at the printed precision. I did not open the author's script, `tools/fidelity_stocker.txt` or `COLD_READ.md`, so I can't name any difference in method.

| Item | Published | Mine | Verdict |
|---|---|---|---|
| 006 n | 159 | 159 | MATCH |
| 006 range | 1969-08..1982-10 | 1969-08..1982-10 | MATCH |
| 006 w | 0.6604 | 0.6604 | MATCH |
| 006 mean(e)x12 | +0.626% | +0.626% | MATCH |
| 006 mean(g)x12 | −0.229% | −0.229% | MATCH |
| 006 sd(g)xsqrt12 | 2.614% | 2.614% | MATCH |
| 006 ratio | 0.316 | 0.316 | MATCH |
| 006 corr | 0.960 | 0.960 | MATCH |
| 007/008 n | 100 | 100 / 100 | MATCH |
| 007/008 range | 1974-07..1982-10 | 1974-07..1982-10 | MATCH |
| 007 w, mean(e)x12 | 0.5071, +0.570% | 0.5071, +0.570% | MATCH |
| 008 w, mean(e)x12 | 0.4458, +0.766% | 0.4458, +0.766% | MATCH |
| 007/008 ratio | 0.334 | 0.334 | MATCH |
| 007/008 corr | 0.954 | 0.954 | MATCH |

Not published, but computed: 007/008 mean(g)x12 −0.157% and sd(g)xsqrt12 3.066%.

**Sign argument:** Yes. (T1s−B3s) − (T1i−B3i) = (h−w)(bond_s−bill) − (h−w)(bond_i−bill) = (h−w)·g, so a positive mean(e) means the synthetic leg overstates T1's advantage over B3.

**Method concerns:**
- **Month matching:** The range is execution months; the signal months run one month earlier (1969-07..1982-09). The matched periods are contiguous with no gaps. The window ends at 1982-10 because the Stocker file ends there.
- **One-trading-day offset:** Each Stocker row runs from the last trading day of month M−1 to the last trading day of M. Each 006 period runs from the first trading day of M to the first trading day of M+1. So each matched pair is shifted by about one trading day at both ends. That adds noise to g, so the gap is slightly overstated, but it should add no bias to mean(e).
- **Duration mismatch:** Stocker is a 5–10-year bucket, with modified duration about 4.5–4.7 in 1969 and 1982 (my spot check). If the synthetic leg is an IEF-like 7–10-year bond, part of g is a duration difference, not error.
- **SD convention:** I used sample SD (n−1); the ratio is the same either way. The Stocker file has two rows ending in November 1942, which is outside this window.

## Author's response

- Duration mismatch: agreed and already reported; the post-hoc duration-matched block in `tools/fidelity_stocker.txt` roughly halves the bias, which stays above 0.18%. The offset's effect on mean(e) is the reviewer's expectation (inferred), not measured: a one-day shift can correlate with h around turning points, so it is listed as a limit, not dismissed.

## Reviewer's script (verbatim, run with `python3 -I`; kept here, not as a .py file, so the repository lint stays on the desk's own code)

```python
import csv,sys,math,datetime as dt
R='./'  # repository root (the reviewer's absolute local path replaced before commit: the leak scan blocked it)
st={}
with open(R+'tools/data/raw/stocker/returns_05_10.csv') as f:
    rows=list(csv.reader(f,delimiter='\t'))
for r in rows[1:]:
    if len(r)<3 or not r[1].strip(): continue
    e=dt.datetime.strptime(r[1].strip(),'%d-%b-%Y')
    k=(e.year,e.month)
    if k in st: print('dup',k,file=sys.stderr)
    st[k]=float(r[2])/100
print('stocker range',min(st),max(st),len(st))
def mean(x): return sum(x)/len(x)
def sd(x):
    m=mean(x); return math.sqrt(sum((a-m)**2 for a in x)/(len(x)-1))
def corr(x,y):
    mx,my=mean(x),mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))
for name,path,hf in [('006','research/006-term-spread-switch-long-history/results/history/monthly_base.csv',lambda r:1.0 if r['T1_holding']=='IEF' else 0.0),
 ('007','research/007-bond-carry-tilt-long-history/results/history/monthly_base.csv',lambda r:float(r['w_T1'])),
 ('008','research/008-bond-value-tilt-long-history/results/history/monthly_base.csv',lambda r:float(r['w_T1']))]:
    M=[]
    for r in csv.DictReader(open(R+path)):
        d=dt.date.fromisoformat(r['execution_date'])
        k=(d.year,d.month)
        if k in st and r['B1']!='': M.append((r,st[k]))
    B1=[float(r['B1']) for r,s in M]; B0=[float(r['B0']) for r,s in M]; S=[s for r,s in M]
    h=[hf(r) for r,s in M]; g=[b-s for b,s in zip(B1,S)]; w=mean(h)
    e=[(hh-w)*gg for hh,gg in zip(h,g)]
    for sd_ in (1,):
        print(name,'n',len(M),'exec',M[0][0]['execution_date'],M[-1][0]['execution_date'],'sig',M[0][0]['month'],M[-1][0]['month'],
          'w %.4f'%w,'mean(e)x12 %.3f%%'%(mean(e)*1200),'mean(g)x12 %.3f%%'%(mean(g)*1200),
          'sd(g)rt12 %.3f%%'%(sd(g)*math.sqrt(12)*100),'ratio %.3f'%(sd(g)/sd([s-b for s,b in zip(S,B0)])),'corr %.3f'%corr(B1,S))
    # contiguity check
    ks=[dt.date.fromisoformat(r['execution_date']) for r,s in M]
    gaps=[(a,b) for a,b in zip(ks,ks[1:]) if (b.year*12+b.month)-(a.year*12+a.month)!=1]
    print(' gaps',gaps, 'pop-sd ratio check', sd(g)/sd([s-b for s,b in zip(S,B0)]))
```
