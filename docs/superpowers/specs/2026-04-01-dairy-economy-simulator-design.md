# Moomoo — Dairy Economy Simulator Design

## Overview

A browser-based interactive dairy processing economy simulator. The user configures a mini dairy supply chain — milk producer, separator, butter plants, cheese plants — and watches production volumes, component flows, and commodity prices evolve in real time via a fast-running tick simulation.

The core purpose is understanding how configuration changes (cow milk composition, separator settings, cheese type selection, butter fat targets) ripple through the entire dairy complex via mass balance constraints, and how the resulting production mix affects commodity prices through supply/demand dynamics.

## System Architecture

### Approach: Simulation Engine + Separate UI

Two distinct layers:

1. **Simulation engine** — pure TypeScript, no UI dependencies. Owns the tick loop, mass balance math, and pricing model. Testable in isolation.
2. **UI layer** — React dashboard that reads engine state each tick and renders it. Sends config changes back to the engine.

The engine exposes a simple interface: `tick(config) → state`. The UI calls `tick()` in a `requestAnimationFrame` or `setInterval` loop, reads the returned state, and renders.

## Processing Flow

```
Milk Producer
    │ whole milk (fat + SNF + water)
    ▼
Milk Separator (target cream fat %)
    ├── cream ──────────────┐
    └── skim                │
         │                  │
    ┌────┴────┐             │
    ▼         ▼             │
Cheese A   Cheese B         │
    │         │             │
    ├── excess cream ──────►│
    │         │             │
    ▼         ▼             ▼
  cheese    cheese      Cream Pool
  + whey    + whey     (separator cream
                        + cheese excess)
                            │
                       ┌────┴────┐
                       ▼         ▼
                   Butter A   Butter B
                       │         │
                       ▼         ▼
                    butter     butter
                   + powder   + powder
```

Key dynamic: cheese type selection affects excess cream sent to butter plants, which affects butter/powder output, which affects prices. Changing one parameter ripples through the whole system.

## Mass Balance

### Three-Component Model

Every stream is represented as `{ volume, fat, snf, water }` where `fat + snf + water = volume`.

Mass balance is enforced at every node: `component_in = component_out` for fat, SNF, and water independently. Any discrepancy is tracked as a residual stream and surfaced in the UI.

### Separator

- Input: whole milk `M` with fat fraction `f_m`
- Target: cream fat fraction `f_c` (configurable, typically 0.35–0.42)
- Skim fat fraction `f_s` (fixed at ~0.001)
- Cream volume: `C = M × (f_m - f_s) / (f_c - f_s)`
- Skim volume: `S = M - C`
- SNF and water distribute proportionally to volume

### Cheese Plants

- Each cheese type has a target casein-to-fat ratio for standardization
- Plant receives skim, calculates fat to retain vs send to cream pool
- Cheese yield via Van Slyke-style formula: `yield = (fat_recovered + casein_recovered) × moisture_factor`
- Whey = input - cheese (mass balance)
- Cheese types and approximate parameters:

| Type | Moisture % | Fat Recovery % | Casein:Fat Ratio | Notes |
|------|-----------|----------------|-----------------|-------|
| Cheddar | 37 | 90 | 0.68 | High fat, standard |
| Mozzarella | 47 | 85 | 0.95 | High moisture, stretched |
| Swiss | 38 | 88 | 0.80 | Medium fat |
| Parmesan | 30 | 88 | 1.20 | Low moisture, hard |

### Butter Plants

- Cream → churn → butter (target fat %, typically 80–82%) + buttermilk
- Butter volume: `B = cream_fat / target_butter_fat`
- Buttermilk = cream - butter (mass balance)
- Buttermilk → dry into selected powder type:
  - **NFDM/SMP** — standard dried buttermilk (non-fat dry milk)
  - **BMP** — buttermilk powder (distinct product, higher phospholipid content)
  - **WMP** — whole milk powder (requires adding fat back before drying)

## Market / Pricing Model

Each product has:

- **Base price** — realistic default $/lb
- **Demand** — target demand quantity per tick (fixed for v1)
- **Elasticity** — price sensitivity to supply/demand imbalance

Price formula: `price = base_price × (demand / supply) ^ elasticity`

Products tracked: butter, NFDM, BMP, WMP, cheddar, mozzarella, swiss, parmesan, whey.

No inventory or storage for v1 — everything produced in a tick is sold at that tick's price.

Revenue per tick = sum of `product_volume × product_price` across all outputs.

## Configuration Parameters

| Node | Parameters |
|------|-----------|
| Milk Producer | Fat % (3.0–5.0), SNF % (7.5–9.5), production rate (constant for v1) |
| Separator | Target cream fat % |
| Cream allocation | % split to Butter Plant A vs B |
| Skim allocation | % split to Cheese Plant A vs B |
| Butter Plant A/B | Target butter fat %, powder type (NFDM/BMP/WMP) |
| Cheese Plant A/B | Cheese type (Cheddar/Mozzarella/Swiss/Parmesan) |
| Simulation | Ticks per second, play/pause |

All parameters are mutable at any tick — change a slider and the next tick uses the new value.

## UI Layout

Single-page web app with two main areas:

### Left Panel — Controls
- Sliders and dropdowns for all configuration parameters listed above
- Simulation speed control and play/pause

### Right Panel — Dashboard
- **Flow diagram** — simplified processing flow with live numbers on each stream (volumes, compositions, updating each tick)
- **Production bar charts** — output volumes per product, updating live
- **Price tickers** — current price per product with sparkline showing recent trend
- **Mass balance audit** — table showing total fat/SNF/water in vs out, residuals highlighted
- **Revenue** — total $/tick and breakdown by product

## Tech Stack

- **Engine:** TypeScript, pure functions, no dependencies
- **UI:** React + Vite
- **Charts:** uPlot for sparklines/time series, or plain Canvas/SVG for bar charts
- **State:** React state + useRef for engine instance
- **Styling:** CSS modules or plain CSS
- **Testing:** Vitest for engine unit tests

No backend. Everything client-side.

## Future Phases (Out of Scope for v1)

- Variable milk production rate (seasonal, configurable curves)
- US-style decentralized model (plants receive whole milk, do own separation, trade cream)
- Whey processing (WPC, WPI, whey powder, lactose)
- Dynamic demand curves
- Inventory/storage mechanics
- Historical CME price data integration
