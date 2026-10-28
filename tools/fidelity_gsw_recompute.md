# Separate recomputation of `tools/fidelity_gsw.txt` (2026-10-28)

A separate Opus 5.5 agent, briefed with the twin's specification only, wrote its own code from the three raw files without opening `fidelity_gsw.py` or its output. It wrote nothing in the repository. Because it worked from the same written specification, it checks the arithmetic and the data handling, not the choice of check.

| Figure (Study 006) | `fidelity_gsw.txt` | Recomputed |
|---|---|---|
| Valid days | 13,768 (1971-08-16..2026-10-23) | 13,768 (1971-08-16..2026-10-23) |
| B: n | 240 | 240 |
| B: mean(g) × 12 | −0.249% | −0.2494% |
| B: sd(g) × √12 | 0.754% | 0.7545% |
| B: signed G1-style | −0.011% | −0.0107% |
| B: G2-style | 0.102 | 0.1024 |
| A: months | 134 (1971-09..1982-10) | 134 (1971-09..1982-10) |
| A: signed G1, leg vs Stocker | +0.617% | +0.6169% |
| A: signed G1, twin vs Stocker | +0.582% | +0.5822% |
| A: share | 0.94 | 0.9438 |
| Twin 1995 (by execution month) | +24.18% | +24.18% |
| Twin 2002 | +16.04% | +16.04% |

**Result: match on every figure.** Ambiguities the reader resolved, all the same way as the script: months keyed by execution month; the first twin month is 1971-09, because the index starts on 1971-08-16; BETA3 = 0 when BETA3 or TAU2 is missing; a calendar year compounds the twelve periods that execute in it.

Recomputation code (pure Python, run with `python3 -I`; the absolute path prefix in `R` was replaced by the repository root for publication, nothing else changed):

```python
import csv, math, statistics as st, datetime as dt
R=''  # run from the repository root
GSW=R+'tools/data/raw/gsw/feds200628.csv'
BASE=R+'research/006-term-spread-switch-long-history/results/history/monthly_base.csv'
STK=R+'tools/data/raw/stocker/returns_05_10.csv'
def num(x):
    x=(x or '').strip()
    if x in ('','NA'): return None
    try: return float(x)
    except ValueError: return None
# ---- GSW valid days
lines=open(GSW).read().splitlines()
h0=next(i for i,l in enumerate(lines) if l.startswith('Date'))
rd=csv.DictReader(lines[h0:])
days=[]
for r in rd:
    try: d=dt.date.fromisoformat(r['Date'].strip())
    except ValueError: continue
    b0,b1,b2,t1=(num(r[k]) for k in ('BETA0','BETA1','BETA2','TAU1'))
    if num(r['SVENY09']) is None or None in (b0,b1,b2,t1): continue
    b3,t2=num(r['BETA3']),num(r['TAU2'])
    if b3 is None or t2 is None: b3,t2=0.0,1.0   # NS fallback; t2 irrelevant when b3=0
    days.append((d,(b0,b1,b2,b3,t1,t2)))
days.sort()
def D(p,n):
    b0,b1,b2,b3,t1,t2=p
    if n<=0: return 1.0
    f1=(1-math.exp(-n/t1))/(n/t1); f2=(1-math.exp(-n/t2))/(n/t2)
    z=b0+b1*f1+b2*(f1-math.exp(-n/t1))+b3*(f2-math.exp(-n/t2))
    return math.exp(-z/100*n)
idx=[(days[0][0],1.0)]; I=1.0
for (s,ps),(t,pt) in zip(days,days[1:]):
    yf=(t-s).days/365
    c=2*(1-D(ps,8.5))/sum(D(ps,0.5*k) for k in range(1,18))
    P=c/2*sum(D(pt,0.5*k-yf) for k in range(1,18))+D(pt,8.5-yf)
    I*=P-0.0015*yf          # 1 + r
    idx.append((t,I))
import bisect
dkeys=[d for d,_ in idx]
def Iat(dstr):
    d=dt.date.fromisoformat(dstr); j=bisect.bisect_right(dkeys,d)-1
    return None if j<0 else idx[j][1]
# ---- study rows
rows=list(csv.DictReader(open(BASE)))
for r in rows:
    a,b=Iat(r['execution_date']),Iat(r['period_end'])
    r['twin']=None if a is None or b is None else b/a-1
    r['em']=r['execution_date'][:7]; r['h']=1.0 if r['T1_holding']=='IEF' else 0.0
    r['B1']=float(r['B1']); r['B0']=float(r['B0'])
# ---- Stocker
stk={}
for r in csv.DictReader(open(STK),delimiter='\t'):
    e=dt.datetime.strptime(r['End'].strip(),'%d-%b-%Y'); stk[e.strftime('%Y-%m')]=float(r['Return(%)'])/100
def stats(sel,comp,base='B1'):
    g=[r[base]-comp(r) for r in sel]; h=[r['h'] for r in sel]; w=st.mean(h)
    G1=st.mean([(hi-w)*gi for hi,gi in zip(h,g)])*12
    G2=st.stdev(g)/st.stdev([comp(r)-r['B0'] for r in sel])
    return len(g),st.mean(g)*12,st.stdev(g)*math.sqrt(12),G1,G2
print('first GSW valid day',days[0][0],' last',days[-1][0],' nvalid',len(days))
# 1. Window B
wb=[r for r in rows if '1983-01'<=r['em']<='2002-12']
assert all(r['twin'] is not None for r in wb)
print('Window B n=%d mean_g*12=%.6f sd_g*sqrt12=%.6f G1=%.6f G2=%.6f'%stats(wb,lambda r:r['twin']))
# 2. Calibration
first=min(r['em'] for r in rows if r['twin'] is not None)
cal=[r for r in rows if first<=r['em']<='1982-10' and r['twin'] is not None and r['em'] in stk]
for r in cal: r['stk']=stk[r['em']]
a=stats(cal,lambda r:r['stk'])[3]; b=stats(cal,lambda r:r['stk'],base='twin')[3]
print('Calib first em=%s n=%d (%s..%s) G1(B1 vs Stk)=%.6f G1(twin vs Stk)=%.6f share=%.4f'%(first,len(cal),cal[0]['em'],cal[-1]['em'],a,b,b/a))
# 3. calendar years
for y in ('1995','2002'):
    sel=[r for r in rows if r['em'][:4]==y]; p=1.0
    for r in sel: p*=1+r['twin']
    pb=1.0
    for r in sel: pb*=1+r['B1']
    print('Twin %s n=%d compounded=%.6f  (B1 same=%.6f)'%(y,len(sel),p-1,pb-1))
```
