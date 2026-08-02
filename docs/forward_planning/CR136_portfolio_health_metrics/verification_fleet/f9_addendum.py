"""F9 addendum — demonstrate (not assert) a long-only book where one Euler risk
share exceeds 100% because a hedge-like holding carries a negative contribution."""
import numpy as np

# 2-name long-only book: dominant high-vol name + strongly negatively correlated hedge
v = np.array([0.70, 0.30])
sig = np.array([0.45, 0.35])
rho = -0.80
S = np.outer(sig, sig) * np.array([[1, rho], [rho, 1]])
var = v @ S @ v
rs = v * (S @ v) / var
print("book: w=(70,30)%, vol=(45,35)%, rho=-0.80")
print(f"sigma_p = {np.sqrt(var)*100:.2f}%")
print(f"risk shares = {np.round(rs*100,2)}  sum = {np.sum(rs)*100:.4f}%")
print(f"max single risk share = {np.max(rs)*100:.2f}%  (>100%: {np.max(rs)>1.0})")
