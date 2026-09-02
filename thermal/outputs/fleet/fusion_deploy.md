# Deployable fusion index: Landsat day + ECOSTRESS night

- scenes: landsat 27597, eco night 18873; mills with eco: 152
- fortnightly r vs UNICA, 2019+ (n=102): Landsat-only **0.461**, fused **0.469**
- ECO era 2021+ (n=83): Landsat-only **0.498**, fused **0.479**; bootstrap delta -0.018, 90% CI [-0.150, +0.118], P(delta>0) = 0.40

## Walk-forward crush model (2019+, official carry)
- {'model': 'landsat-only sat + carry', 'n': 116, 'MAE_Mt': np.float64(3.07), 'MAE_clim_Mt': np.float64(3.93), 'skill_vs_clim': np.float64(0.219), 'corr_z': np.float64(0.533), 'PI80_coverage': np.float64(0.802)}
- {'model': 'fused sat + carry', 'n': 116, 'MAE_Mt': np.float64(2.93), 'MAE_clim_Mt': np.float64(3.93), 'skill_vs_clim': np.float64(0.253), 'corr_z': np.float64(0.55), 'PI80_coverage': np.float64(0.776)}
