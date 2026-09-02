# Deployable fusion index: Landsat day + ECOSTRESS night

- scenes: landsat 27597, eco night 542; mills with eco: 5
- fortnightly r vs UNICA, 2019+ (n=102): Landsat-only **0.461**, fused **0.463**
- ECO era 2021+ (n=83): Landsat-only **0.498**, fused **0.503**; bootstrap delta +0.005, 90% CI [-0.002, +0.012], P(delta>0) = 0.88

## Walk-forward crush model (2019+, official carry)
- {'model': 'landsat-only sat + carry', 'n': 116, 'MAE_Mt': np.float64(3.07), 'MAE_clim_Mt': np.float64(3.93), 'skill_vs_clim': np.float64(0.219), 'corr_z': np.float64(0.533), 'PI80_coverage': np.float64(0.802)}
- {'model': 'fused sat + carry', 'n': 116, 'MAE_Mt': np.float64(3.07), 'MAE_clim_Mt': np.float64(3.93), 'skill_vs_clim': np.float64(0.22), 'corr_z': np.float64(0.533), 'PI80_coverage': np.float64(0.802)}
