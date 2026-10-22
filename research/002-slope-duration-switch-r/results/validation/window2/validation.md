# Validation window 2 (§5.3.4 step 3)

Window 2003-01-02 to 2015-12-31; IEF from the second vendor. Instrument returns only; no rule applied; no cash check on this window.

| Check | Value | Threshold | Pass |
|---|---|---|---|
| A1 | 0.95972 | >= 0.95 | yes |
| A2 | 0.92633 | in [0.8, 1.05] | yes |
| A3 | 0.02016 | <= 0.015 | NO |
| A4 | -0.00008 (ex-ante central estimate -0.0005) | in [-0.0045, 0.0035] | yes |

Descriptive: IEF minus synthetic by calendar year, % p.a.: 2003 +0.23, 2004 -0.27, 2005 +0.29, 2006 +0.14, 2007 -0.70, 2008 -1.37, 2009 +1.03, 2010 +0.30, 2011 +0.18, 2012 -0.36, 2013 +0.12, 2014 +0.37, 2015 -0.06

Duration/convexity cross-check, mean absolute daily error: 0.013 bp (acceptance 0.5 bp, §5.2).

Result: FAILED on window 2.
