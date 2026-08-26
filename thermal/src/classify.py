"""ON/OFF/UNCERTAIN classification of per-scene thermal anomalies.

Two models are fitted and reported:

1. Plain 2-component GMM on the raw anomaly (the brief's baseline). At daytime
   sites this can be dominated by seasonal solar heating, which the day-of-year
   regression check exposes.
2. The primary labeller: a 2-component mixture with a SHARED harmonic seasonal
   term, y = a_k + sum_h(b_h sin + c_h cos)(h * 2*pi*doy/365) + eps_k, fitted by
   EM. Both states share one seasonal cycle; the intercept gap a_1 - a_0 is the
   season-free state signal. Fitted on core_anom (label-free hotspot pixels)
   when available, else on the plant_p95 anomaly.

Separability tiers on the intercept gap: >= min_separation_c -> separable;
>= marginal_separation_c -> marginal (labels emitted with a loud caveat);
below that labels are refused.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.mixture import GaussianMixture


def fit_gmm(values, seed=0):
    """2-component 1-D GMM; returns (means_sorted, stds, posterior cols low/high, model)."""
    x = np.asarray(values, dtype=float).reshape(-1, 1)
    gm = GaussianMixture(n_components=2, n_init=10, random_state=seed).fit(x)
    order = np.argsort(gm.means_.ravel())
    post = gm.predict_proba(x)[:, order]
    return gm.means_.ravel()[order], np.sqrt(gm.covariances_.ravel()[order]), post, gm


def seasonal_design(datetimes, harmonics):
    doy = datetimes.dt.dayofyear.values
    cols = []
    for h in range(1, harmonics + 1):
        w = 2 * np.pi * h * doy / 365.25
        cols += [np.sin(w), np.cos(w)]
    return np.column_stack(cols)


def em_seasonal_mixture(y, C, iters=300, min_sigma=0.5, seed=0):
    """2-component mixture with shared covariate coefficients and per-component
    intercept/variance. Returns (intercepts_sorted, coefs, sigmas, post, weights)."""
    y = np.asarray(y, float)
    n, p = C.shape
    X = np.column_stack([np.ones(n), C])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    a = np.array([beta[0] + np.quantile(r, 0.2), beta[0] + np.quantile(r, 0.8)])
    g = beta[1:]
    sig = np.array([max(r.std(), min_sigma)] * 2)
    w = np.array([0.5, 0.5])
    post = np.full((n, 2), 0.5)
    for _ in range(iters):
        mu = a[None, :] + (C @ g)[:, None]
        pdf = w[None, :] * norm.pdf(y[:, None], mu, sig[None, :]) + 1e-300
        post = pdf / pdf.sum(1, keepdims=True)
        w = post.mean(0)
        W0, W1 = post[:, 0], post[:, 1]
        D = np.zeros((2 + p, 2 + p))
        v = np.zeros(2 + p)
        D[0, 0], D[1, 1] = W0.sum(), W1.sum()
        D[0, 2:] = (W0[:, None] * C).sum(0)
        D[2:, 0] = D[0, 2:]
        D[1, 2:] = (W1[:, None] * C).sum(0)
        D[2:, 1] = D[1, 2:]
        D[2:, 2:] = C.T @ ((W0 + W1)[:, None] * C)
        v[0], v[1] = (W0 * y).sum(), (W1 * y).sum()
        v[2:] = C.T @ ((W0 + W1) * y)
        sol = np.linalg.solve(D, v)
        a, g = sol[:2], sol[2:]
        for k, Wk in enumerate([W0, W1]):
            sig[k] = np.sqrt(max((Wk * (y - a[k] - C @ g) ** 2).sum() / max(Wk.sum(), 1e-9), 1e-4))
        sig = np.maximum(sig, min_sigma)
    order = np.argsort(a)
    return a[order], g, sig[order], post[:, order], w[order]


def label_from_posterior(post_on, thresh):
    lab = np.full(post_on.shape, "UNCERTAIN", dtype=object)
    lab[post_on >= thresh] = "ON"
    lab[post_on <= 1 - thresh] = "OFF"
    return lab


def seasonal_residuals(df, col="anomaly"):
    """Residual of col after pooled OLS on day-of-year sin/cos (the brief's
    leakage check; note a pooled fit absorbs part of a real state offset when
    the OFF scenes cluster in particular years)."""
    C = seasonal_design(df["datetime"], 1)
    X = np.column_stack([np.ones(len(df)), C])
    beta, *_ = np.linalg.lstsq(X, df[col].values, rcond=None)
    return df[col].values - X @ beta + df[col].mean(), beta


def smooth_labels(post_on, window, thresh):
    """Rolling-median posterior -> labels. Aggregation shrinks the variance, so
    the smoothed threshold may be softer than the single-scene one."""
    med = pd.Series(post_on).rolling(window, center=True, min_periods=1).median()
    return np.where(med >= thresh, "ON", np.where(med <= 1 - thresh, "OFF", "UNCERTAIN"))


def run_lengths(df, label_col="label_smooth"):
    periods = []
    cur = None
    for _, r in df.iterrows():
        if cur is None or r[label_col] != cur["state"]:
            if cur is not None:
                periods.append(cur)
            cur = {"state": r[label_col], "start": r["date"], "end": r["date"], "n_scenes": 1}
        else:
            cur["end"] = r["date"]
            cur["n_scenes"] += 1
    if cur is not None:
        periods.append(cur)
    return pd.DataFrame(periods)[["start", "end", "state", "n_scenes"]]


def classify(df, cfg, log=print):
    c = cfg["classify"]
    report = {}
    df = df.copy()

    # --- baseline: plain GMM on raw anomaly + the brief's seasonal check ---
    means, stds, post, gm = fit_gmm(df["anomaly"])
    report["gmm_anomaly_raw"] = {
        "means_c": [round(float(m), 2) for m in means],
        "stds_c": [round(float(s), 2) for s in stds],
        "separation_c": round(float(means[1] - means[0]), 2),
        "weights": [round(float(w), 3) for w in gm.weights_],
    }
    resid, beta = seasonal_residuals(df)
    r_means, _, _, _ = fit_gmm(resid)
    report["seasonal_check"] = {
        "seasonal_amplitude_c": round(float(np.hypot(beta[1], beta[2])), 2),
        "residual_separation_c": round(float(r_means[1] - r_means[0]), 2),
        "residual_separable": bool(r_means[1] - r_means[0] >= c["min_separation_c"]),
    }

    # --- primary: seasonal-mixture on the best available signal ---
    signal = "core_anom" if "core_anom" in df and df["core_anom"].notna().sum() >= 30 else "anomaly"
    fit_df = df[df[signal].notna()]
    C = seasonal_design(fit_df["datetime"], c["seasonal_harmonics"])
    a, g, sig, post, w = em_seasonal_mixture(fit_df[signal].values, C)
    sep = float(a[1] - a[0])
    report["seasonal_mixture"] = {
        "signal": signal,
        "n_fit": len(fit_df),
        "intercepts_c": [round(float(v), 2) for v in a],
        "sigmas_c": [round(float(s), 2) for s in sig],
        "separation_c": round(sep, 2),
        "weights": [round(float(v), 3) for v in w],
    }
    if sep >= c["min_separation_c"]:
        report["separability"] = "separable"
    elif sep >= c["marginal_separation_c"]:
        report["separability"] = "marginal"
        log(
            f"WARNING: season-free separation {sep:.2f} C is below the "
            f"{c['min_separation_c']} C floor - scene labels are LOW CONFIDENCE; "
            "trust smoothed/period-level output and cross-checks, not single scenes."
        )
    else:
        report["separability"] = "not_separable"
        log(
            f"WARNING: season-free separation {sep:.2f} C < "
            f"{c['marginal_separation_c']} C - site not thermally separable, "
            "labels refused."
        )

    df["post_on"] = np.nan
    df.loc[fit_df.index, "post_on"] = post[:, 1]
    if report["separability"] == "not_separable":
        df["label"] = "UNCERTAIN"
        df["label_smooth"] = "UNCERTAIN"
        return df, report

    lab = np.full(len(df), "UNCERTAIN", dtype=object)
    lab[df["post_on"].notna()] = label_from_posterior(
        df["post_on"].dropna().values, c["posterior_thresh"]
    )
    df["label"] = lab
    df["label_smooth"] = smooth_labels(
        df["post_on"].values, c["smooth_window"], c["smooth_posterior_thresh"]
    )
    df.loc[df["post_on"].isna(), "label_smooth"] = "UNCERTAIN"

    # hot_frac GMM as an extra consistency diagnostic
    hf_means, _, hf_post, _ = fit_gmm(df["hot_frac"])
    df["post_on_hotfrac"] = hf_post[:, 1]
    labelled = df["post_on"].notna()
    report["gmm_hot_frac"] = {
        "means": [round(float(m), 3) for m in hf_means],
        "agreement_with_primary": round(
            float(((df["post_on"] > 0.5) == (df["post_on_hotfrac"] > 0.5))[labelled].mean()), 3
        ),
    }
    return df, report
