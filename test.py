import numpy as np


def safe_arccos(x):
    np.arccos(np.clip(x, -1, 1))


safe_arccos(np.float64(0.0))
