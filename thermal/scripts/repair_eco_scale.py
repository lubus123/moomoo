"""One-off repair: undo the erroneous x0.02 rescale on cached ECOSTRESS npz
(files written before the fetcher fix). Idempotent: only touches files whose
LST median is < 100 K (a real Kelvin scene is ~220-330 K)."""
import sys
from pathlib import Path

import numpy as np

roots = sys.argv[1:] or ["data/cache_eco_sugar", "data/cache_eco_dairy", "data/cache_eco_ammonia"]
n_fix = n_ok = 0
for root in roots:
    for npz in Path(root).glob("*/scenes/*.npz"):
        a = dict(np.load(npz))
        med = np.nanmedian(a["lst_k"])
        if np.isfinite(med) and med < 100:
            a["lst_k"] = (a["lst_k"] / 0.02).astype(np.float32)
            np.savez_compressed(npz, **a)
            n_fix += 1
        else:
            n_ok += 1
print(f"repaired {n_fix}, already-correct {n_ok}")
