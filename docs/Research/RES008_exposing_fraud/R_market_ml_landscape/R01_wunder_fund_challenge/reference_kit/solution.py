"""Inference-only stateful ONNX baseline for the public competition kit."""
from pathlib import Path
import os

# These environment limits cover common numerical runtimes.  ONNX Runtime is
# also configured explicitly below, which is the authoritative thread limit.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import onnxruntime as ort


class PredictionModel:
    def __init__(self):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.use_per_session_threads = True
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        self.session = ort.InferenceSession(
            str(Path(__file__).resolve().parent / "baseline.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.current_seq_ix = None
        self.previous_step = None
        self.hidden_0 = np.zeros((1, 1, 128), dtype=np.float32)
        self.hidden_1 = np.zeros((1, 1, 128), dtype=np.float32)

    def predict(self, data_point):
        seq_ix = int(data_point.seq_ix)
        step = int(data_point.step_in_seq)
        if self.current_seq_ix != seq_ix:
            if step != 0:
                raise ValueError("a new sequence must start at step zero")
            self.current_seq_ix = seq_ix
            self.previous_step = None
            self.hidden_0.fill(0.0)
            self.hidden_1.fill(0.0)
        if self.previous_step is not None and step != self.previous_step + 1:
            raise ValueError("rows must arrive in sequence order")
        self.previous_step = step

        state = np.asarray(data_point.state, dtype=np.float32)
        if state.shape != (112,) or not np.isfinite(state).all():
            raise ValueError("expected 112 finite float32 features")
        prediction, self.hidden_0, self.hidden_1 = self.session.run(
            None,
            {
                "features": state.reshape(1, 1, 112),
                "hidden_0": self.hidden_0,
                "hidden_1": self.hidden_1,
            },
        )
        if not data_point.need_prediction:
            return None
        return np.asarray(prediction[0, 0], dtype=np.float32)


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import ScorerStepByStep

    parser = argparse.ArgumentParser()
    parser.add_argument("--validation", required=True)
    args = parser.parse_args()
    print(ScorerStepByStep(args.validation).score(PredictionModel()))
