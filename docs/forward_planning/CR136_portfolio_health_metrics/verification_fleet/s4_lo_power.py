"""CR136 verification — script 4: MC power check of Lo (2002) thresholds.
True annual SR = 1.0, iid Gaussian daily returns. Test H0: SR=0 with
z = SR_hat*sqrt(T)/sqrt(1+SR_hat^2/2), two-sided at 5%.
Expect rejection rate ~50% at T=970 and ~80% at T=1982.
Also MC check of the CI claim: at T=90, empirical SD of annualised SR_hat.
"""
import numpy as np

rng = np.random.default_rng(2002)
SR_d = 1.0 / np.sqrt(252)
sig = 0.01
mu = SR_d * sig
zcrit = 1.959963984540054
R = 50_000

for T in [90, 970, 971, 1982]:
    rej = 0
    srs = []
    chunk = 5_000
    for i in range(0, R, chunk):
        n = min(chunk, R - i)
        x = rng.standard_normal((n, T)) * sig + mu
        m = x.mean(axis=1)
        s = x.std(axis=1, ddof=1)
        sr = m / s
        srs.append(sr)
        z = sr * np.sqrt(T) / np.sqrt(1 + sr**2 / 2)
        rej += (np.abs(z) > zcrit).sum()
    srs = np.concatenate(srs)
    power = rej / R
    se_pow = np.sqrt(power * (1 - power) / R)
    print(f"T={T:>5}: rejection rate = {power*100:5.2f}% (+/- {se_pow*100:.2f}pp MC SE)"
          f"  | SR_hat_ann: mean={srs.mean()*np.sqrt(252):.4f} "
          f"SD={srs.std(ddof=1)*np.sqrt(252):.4f}"
          + (f"  (Lo analytic SE_ann at T=90: "
             f"{np.sqrt((1+SR_d**2/2)/T)*np.sqrt(252):.4f})" if T == 90 else ""))
