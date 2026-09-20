# Scoring reference: Weighted Pearson correlation

Specification ID: `v2_wp_block_clip2_v1`. The score is the equal mean of block-wise,
two-target Weighted Pearson correlations on the supplied scoring mask.
Both targets refer to instrument `i0`.

## Evaluation domain

Each sequence contains exactly 20,000 rows. Steps 0 through 98 are warm-up;
every later step requires two finite, float32-compatible predictions. Model
state must be updated on every row and reset between sequences. Scoring uses
only `need_prediction AND is_scored`, without filtering the inference stream.
The `is_scored` column marks the rows used for evaluation.

For this challenge, a block is eligible only if, on its selected rows, each
target has at least one strictly positive and one strictly negative value.
Otherwise the whole block is excluded. Eligibility depends on the targets and
mask. A block with an empty mask is excluded.
If no blocks are eligible, evaluation fails instead of returning a score.

All required predictions must still be valid, even in excluded blocks or on
unscored rows. Missing outputs, incorrect shapes, or nonfinite values are
submission errors, not additional reasons to exclude data.

## Per-target WP

For sequence `b`, let `M_b` contain only rows where
`need_prediction AND is_scored` is true. For target `k`, clip both the target
and prediction on those selected rows:

$$
y_{bki}=\operatorname{clip}(t_{bki},-2,2),\qquad
\hat y_{bki}=\operatorname{clip}(p_{bki},-2,2),\qquad i\in M_b.
$$

With $w_{bki}=|y_{bki}|$ and $W_{bk}=\sum_{i\in M_b}w_{bki}$, define

$$
\bar y_{bk,w}=\frac{\sum_{i\in M_b}w_{bki}y_{bki}}{W_{bk}},\qquad
\bar{\hat y}_{bk,w}=\frac{\sum_{i\in M_b}w_{bki}\hat y_{bki}}{W_{bk}},
$$

$$
\operatorname{cov}_{bk,w}=
\frac{\sum_{i\in M_b}w_{bki}(y_{bki}-\bar y_{bk,w})
(\hat y_{bki}-\bar{\hat y}_{bk,w})}{W_{bk}},
$$

$$
\operatorname{var}_{bk,w}(y)=
\frac{\sum_{i\in M_b}w_{bki}(y_{bki}-\bar y_{bk,w})^2}{W_{bk}},\qquad
\operatorname{var}_{bk,w}(\hat y)=
\frac{\sum_{i\in M_b}w_{bki}(\hat y_{bki}-\bar{\hat y}_{bk,w})^2}{W_{bk}},
$$

$$
\rho_{bk,w}=
\frac{\operatorname{cov}_{bk,w}}
{\sqrt{\operatorname{var}_{bk,w}(y)\operatorname{var}_{bk,w}(\hat y)}}.
$$

Each target uses the absolute value of its clipped target as weight. Zero
targets have zero weight. Clipping is part of scoring only: stored targets
and submitted predictions are not changed.

Use float32-compatible inputs and float64 metric accumulation. If `W < 1e-8`,
or either weighted standard deviation is at most `1e-8`, the side contributes
`0`. Constant predictions also contribute `0`; the block remains included.
The returned correlation is bounded to `[-1, 1]` only to remove numerical
round-off outside the mathematical range.

## Aggregation

$$
s_b=\frac{\rho_{b,0,w}+\rho_{b,1,w}}{2},\qquad
S=\frac{1}{|B|}\sum_{b\in B}s_b,
$$

where `B` is the set of eligible 20,000-row sequences.

Both targets and all eligible sequences have equal weight in the final score.
The result lies in `[-1, 1]`; higher is better.

## Standalone reference calculation

`block_wp` accepts a complete 20,000-row block and returns `None` for an
ineligible block. The callback contract is described in
[Submission guide](docs/submission_guide.md).

```python
import numpy as np

METRIC_CLIP = 2.0


def weighted_pearson(target, prediction):
    y = np.asarray(target, dtype=np.float32)
    p = np.asarray(prediction, dtype=np.float32)
    if y.ndim != 1 or p.shape != y.shape:
        raise ValueError("expected equal one-dimensional arrays")
    if not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("nonfinite target or prediction")
    y = np.clip(y, -METRIC_CLIP, METRIC_CLIP).astype(np.float64)
    p = np.clip(p, -METRIC_CLIP, METRIC_CLIP).astype(np.float64)
    w = np.abs(y)
    total = w.sum()
    if total < 1e-8:
        return 0.0
    mean_y = np.sum(w * y) / total
    mean_p = np.sum(w * p) / total
    yc, pc = y - mean_y, p - mean_p
    cov = np.sum(w * yc * pc) / total
    sy = np.sqrt(np.sum(w * yc * yc) / total)
    sp = np.sqrt(np.sum(w * pc * pc) / total)
    if sy <= 1e-8 or sp <= 1e-8:
        return 0.0
    return float(np.clip(cov / (sy * sp), -1.0, 1.0))


def block_wp(targets, predictions, is_scored):
    y = np.asarray(targets, dtype=np.float32)
    p = np.asarray(predictions, dtype=np.float32)
    mask = np.asarray(is_scored, dtype=bool)
    if y.shape != (20_000, 2) or p.shape != y.shape:
        raise ValueError("expected targets and predictions of shape (20000, 2)")
    if mask.shape != (20_000,) or mask[:99].any():
        raise ValueError("invalid mask or selected warm-up rows")
    if not np.isfinite(y).all() or not np.isfinite(p[99:]).all():
        raise ValueError("nonfinite target or required prediction")
    selected = mask & (np.arange(20_000) >= 99)
    if not all(np.any(y[selected, j] > 0) and np.any(y[selected, j] < 0)
               for j in range(2)):
        return None
    return float(np.mean([weighted_pearson(y[selected, j], p[selected, j])
                          for j in range(2)]))


def aggregate_wp(block_scores):
    scores = [s for s in block_scores if s is not None]
    if not scores:
        raise ValueError("no eligible blocks")
    if not np.isfinite(scores).all():
        raise ValueError("nonfinite block score")
    return float(np.mean(scores, dtype=np.float64))
```

The evaluation report should include per-target WP, final WP, total/eligible/
excluded block counts, selected rows and rows in eligible blocks. These counts
make the evaluation domain auditable; they do not change the weighting.
