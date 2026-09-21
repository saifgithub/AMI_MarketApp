"""
First-look exploration of the Wunder Fund 'Alpha Connectome' challenge data.
Read-only analysis: inspects schema, target distributions, and basic
per-feature correlation with t0/t1 on a sample of sequences, without
training anything. Purpose: verify the primary-source docs against the
actual data, and see if t0/t1's undisclosed definition can be inferred
from their statistical behavior (e.g. horizon, scale, relationship to
price-level features).

The dataset itself (~31GB extracted) is NOT committed to this repo — it's a
public, unauthenticated download (see VERDICT.md). Re-fetch it with:
  curl -L https://files.wundernn.io/wnn_connectome_starterpack.tar.gz | tar -xz
then set WUNDER_DATA_DIR to the extracted `datasets/` folder before running
this script (defaults to `./wnn_connectome_starterpack/datasets` if unset).
Findings from the 2026-09-20/21 run are recorded in VERDICT.md's "Actual data
findings" section.
"""
import os
import sys
import numpy as np
import pyarrow.parquet as pq

DATA_DIR = os.environ.get("WUNDER_DATA_DIR", "wnn_connectome_starterpack/datasets")

FEATURE_COLUMNS = [f'i{i}_{g}{j}' for i in range(2)
                   for g, n in [('p', 22), ('v', 22), ('dp', 4), ('dv', 4)] for j in range(n)]
FEATURE_COLUMNS += [f'a{i}' for i in range(8)]
TARGET_COLUMNS = ('t0', 't1')


def main(n_sequences=50):
    pf = pq.ParquetFile(f"{DATA_DIR}/train.parquet")
    print(f"Total row groups (sequences) in train.parquet: {pf.num_row_groups}")
    print(f"Schema: {pf.schema_arrow.names}")
    print()

    all_targets = []
    all_features = []
    for i in range(min(n_sequences, pf.num_row_groups)):
        table = pf.read_row_group(i)
        t0 = table['t0'].to_numpy()
        t1 = table['t1'].to_numpy()
        need = table['need_prediction'].to_numpy().astype(bool)
        all_targets.append(np.column_stack([t0[need], t1[need]]))
        feats = np.column_stack([table[c].to_numpy()[need] for c in FEATURE_COLUMNS])
        all_features.append(feats)

    targets = np.concatenate(all_targets, axis=0)
    features = np.concatenate(all_features, axis=0)
    print(f"Sampled {n_sequences} sequences -> {targets.shape[0]} scored-eligible rows")
    print()

    for j, name in enumerate(TARGET_COLUMNS):
        col = targets[:, j]
        print(f"--- {name} ---")
        print(f"  mean={col.mean():.6f}  std={col.std():.6f}  min={col.min():.4f}  max={col.max():.4f}")
        print(f"  pct near zero (|x|<1e-6): {np.mean(np.abs(col) < 1e-6)*100:.2f}%")
        print(f"  pct positive: {np.mean(col > 0)*100:.2f}%  pct negative: {np.mean(col < 0)*100:.2f}%")

    print()
    print("Correlation of each feature with t0 (top 10 by |corr|):")
    corrs = []
    for k, name in enumerate(FEATURE_COLUMNS):
        c = np.corrcoef(features[:, k], targets[:, 0])[0, 1]
        corrs.append((name, c))
    corrs.sort(key=lambda x: -abs(x[1]) if np.isfinite(x[1]) else 0)
    for name, c in corrs[:10]:
        print(f"  {name}: {c:.4f}")

    print()
    print("Correlation between t0 and t1:", np.corrcoef(targets[:, 0], targets[:, 1])[0, 1])


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    main(n)
