# Dairy Economy Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive browser-based dairy processing economy simulator with mass balance tracking, configurable plants, and supply/demand pricing.

**Architecture:** Pure TypeScript simulation engine (no UI deps) orchestrates a tick loop through: milk producer → separator → cheese plants (with cream recirculation) → butter plants → market pricing. React UI renders live dashboard with controls. Engine and UI are fully decoupled — engine exposes `tick(config) → state`.

**Tech Stack:** TypeScript, React, Vite, Vitest, uPlot (sparklines), CSS

**User Verification:** NO — no user verification required

---

## File Structure

```
src/
  engine/
    types.ts          — Stream, Config, SimulationState, cheese/powder enums
    producer.ts       — milk production (constant rate, configurable composition)
    separator.ts      — centrifugal separation mass balance
    cheese-plant.ts   — standardization, Van Slyke yield, whey output
    butter-plant.ts   — churning, buttermilk, powder drying
    market.ts         — supply/demand pricing per product
    simulation.ts     — tick orchestrator wiring all nodes
  ui/
    App.tsx           — layout shell, simulation loop, state management
    Controls.tsx      — left panel: all sliders and dropdowns
    FlowDiagram.tsx   — SVG flow diagram with live stream numbers
    ProductionChart.tsx — bar charts for output volumes
    PriceTicker.tsx   — price display with sparklines
    MassBalance.tsx   — fat/SNF/water audit table
    Revenue.tsx       — revenue breakdown table
  main.tsx            — React entry point
  index.css           — dashboard styles
tests/
  engine/
    producer.test.ts
    separator.test.ts
    cheese-plant.test.ts
    butter-plant.test.ts
    market.test.ts
    simulation.test.ts
index.html
package.json
tsconfig.json
vite.config.ts
```

---

### Task 0: Project Scaffolding

**Goal:** Set up Vite + React + TypeScript project with Vitest configured.

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `index.html`
- Create: `src/main.tsx`
- Create: `src/index.css`

**Acceptance Criteria:**
- [ ] `npm run dev` starts dev server with hot reload
- [ ] `npm test` runs Vitest
- [ ] TypeScript strict mode enabled

**Verify:** `npm test -- --run` → "No test suites found" (no tests yet, but runner works)

**Steps:**

- [ ] **Step 1: Initialize project**

```bash
cd /workspace/moomoo
npm init -y
npm install react react-dom
npm install -D typescript vite @vitejs/plugin-react vitest @types/react @types/react-dom
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "react-jsx",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": ".",
    "baseUrl": ".",
    "paths": {
      "@engine/*": ["src/engine/*"],
      "@ui/*": ["src/ui/*"]
    }
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@engine': path.resolve(__dirname, 'src/engine'),
      '@ui': path.resolve(__dirname, 'src/ui'),
    },
  },
  test: {
    globals: true,
  },
});
```

- [ ] **Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Moomoo — Dairy Economy Simulator</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

- [ ] **Step 5: Create src/main.tsx**

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';

function App() {
  return <div>Moomoo</div>;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 6: Create src/index.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; }
#root { width: 100vw; height: 100vh; }
```

- [ ] **Step 7: Verify and commit**

```bash
npm run dev -- --host 0.0.0.0 &
sleep 2
curl -s http://localhost:5173 | head -5
kill %1
npm test -- --run 2>&1 || true
git add -A
git commit -m "chore: scaffold Vite + React + TypeScript project with Vitest"
```

---

### Task 1: Engine Types

**Goal:** Define all TypeScript types for the simulation engine — streams, config, state, enums.

**Files:**
- Create: `src/engine/types.ts`
- Create: `tests/engine/types.test.ts`

**Acceptance Criteria:**
- [ ] Stream type enforces `fat + snf + water = volume` via helper
- [ ] All config parameters from spec are represented
- [ ] SimulationState contains all node outputs and market prices

**Verify:** `npx vitest run tests/engine/types.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests for stream creation and validation**

```typescript
// tests/engine/types.test.ts
import { describe, it, expect } from 'vitest';
import { createStream, validateStream, CheeseType, PowderType } from '../src/engine/types';

describe('Stream', () => {
  it('creates a stream with correct volume', () => {
    const s = createStream(100, 0.04, 0.09);
    expect(s.fat).toBeCloseTo(4);
    expect(s.snf).toBeCloseTo(9);
    expect(s.water).toBeCloseTo(87);
    expect(s.volume).toBeCloseTo(100);
  });

  it('validates mass closure', () => {
    const s = createStream(100, 0.04, 0.09);
    expect(validateStream(s)).toBe(true);
  });

  it('detects invalid stream', () => {
    expect(validateStream({ volume: 100, fat: 50, snf: 50, water: 50 })).toBe(false);
  });
});

describe('Enums', () => {
  it('has all cheese types', () => {
    expect(Object.values(CheeseType)).toEqual(['cheddar', 'mozzarella', 'swiss', 'parmesan']);
  });

  it('has all powder types', () => {
    expect(Object.values(PowderType)).toEqual(['nfdm', 'bmp', 'wmp']);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npx vitest run tests/engine/types.test.ts
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement types**

```typescript
// src/engine/types.ts

export interface Stream {
  volume: number; // total mass (lbs)
  fat: number;    // fat mass (lbs)
  snf: number;    // solids-not-fat mass (lbs)
  water: number;  // water mass (lbs)
}

export function createStream(volume: number, fatFraction: number, snfFraction: number): Stream {
  const fat = volume * fatFraction;
  const snf = volume * snfFraction;
  const water = volume - fat - snf;
  return { volume, fat, snf, water };
}

export function validateStream(s: Stream): boolean {
  return Math.abs(s.fat + s.snf + s.water - s.volume) < 0.001;
}

export const EMPTY_STREAM: Stream = { volume: 0, fat: 0, snf: 0, water: 0 };

export function addStreams(...streams: Stream[]): Stream {
  const result = { volume: 0, fat: 0, snf: 0, water: 0 };
  for (const s of streams) {
    result.volume += s.volume;
    result.fat += s.fat;
    result.snf += s.snf;
    result.water += s.water;
  }
  return result;
}

export enum CheeseType {
  Cheddar = 'cheddar',
  Mozzarella = 'mozzarella',
  Swiss = 'swiss',
  Parmesan = 'parmesan',
}

export enum PowderType {
  NFDM = 'nfdm',
  BMP = 'bmp',
  WMP = 'wmp',
}

export interface ProducerConfig {
  fatPercent: number;       // 3.0–5.0
  snfPercent: number;       // 7.5–9.5
  productionRate: number;   // lbs per tick
}

export interface SeparatorConfig {
  targetCreamFatPercent: number; // 35–42
}

export interface ButterPlantConfig {
  targetButterFatPercent: number; // 78–84
  powderType: PowderType;
}

export interface CheesePlantConfig {
  cheeseType: CheeseType;
}

export interface SimulationConfig {
  producer: ProducerConfig;
  separator: SeparatorConfig;
  skimSplitPercent: number;     // % of skim to Cheese Plant A (rest to B)
  creamSplitPercent: number;    // % of cream pool to Butter Plant A (rest to B)
  butterPlantA: ButterPlantConfig;
  butterPlantB: ButterPlantConfig;
  cheesePlantA: CheesePlantConfig;
  cheesePlantB: CheesePlantConfig;
}

export interface ProductPrices {
  butter: number;
  nfdm: number;
  bmp: number;
  wmp: number;
  cheddar: number;
  mozzarella: number;
  swiss: number;
  parmesan: number;
  whey: number;
}

export interface ProductVolumes {
  butter: number;
  nfdm: number;
  bmp: number;
  wmp: number;
  cheddar: number;
  mozzarella: number;
  swiss: number;
  parmesan: number;
  whey: number;
}

export interface NodeOutputs {
  wholeMilk: Stream;
  cream: Stream;
  skim: Stream;
  cheesePlantA: { cheese: Stream; whey: Stream; excessCream: Stream };
  cheesePlantB: { cheese: Stream; whey: Stream; excessCream: Stream };
  creamPool: Stream;
  butterPlantA: { butter: Stream; powder: Stream };
  butterPlantB: { butter: Stream; powder: Stream };
}

export interface SimulationState {
  tick: number;
  config: SimulationConfig;
  nodes: NodeOutputs;
  production: ProductVolumes;
  prices: ProductPrices;
  revenue: number;
  massBalanceError: { fat: number; snf: number; water: number };
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/engine/types.test.ts
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/engine/types.ts tests/engine/types.test.ts
git commit -m "feat: add engine types — streams, config, state, enums"
```

---

### Task 2: Milk Producer

**Goal:** Implement milk production — generates a whole milk stream from config.

**Files:**
- Create: `src/engine/producer.ts`
- Create: `tests/engine/producer.test.ts`

**Acceptance Criteria:**
- [ ] Produces stream with correct fat/SNF/water from config percentages
- [ ] Mass balance validates on output

**Verify:** `npx vitest run tests/engine/producer.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests**

```typescript
// tests/engine/producer.test.ts
import { describe, it, expect } from 'vitest';
import { produce } from '../src/engine/producer';
import { validateStream } from '../src/engine/types';

describe('producer', () => {
  it('produces whole milk with correct composition', () => {
    const milk = produce({ fatPercent: 4.0, snfPercent: 9.0, productionRate: 1000 });
    expect(milk.volume).toBe(1000);
    expect(milk.fat).toBeCloseTo(40);
    expect(milk.snf).toBeCloseTo(90);
    expect(milk.water).toBeCloseTo(870);
    expect(validateStream(milk)).toBe(true);
  });

  it('handles high fat jersey cows', () => {
    const milk = produce({ fatPercent: 5.0, snfPercent: 9.5, productionRate: 500 });
    expect(milk.fat).toBeCloseTo(25);
    expect(milk.snf).toBeCloseTo(47.5);
    expect(milk.water).toBeCloseTo(427.5);
    expect(validateStream(milk)).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
npx vitest run tests/engine/producer.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// src/engine/producer.ts
import { Stream, ProducerConfig, createStream } from './types';

export function produce(config: ProducerConfig): Stream {
  return createStream(
    config.productionRate,
    config.fatPercent / 100,
    config.snfPercent / 100,
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npx vitest run tests/engine/producer.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/producer.ts tests/engine/producer.test.ts
git commit -m "feat: add milk producer"
```

---

### Task 3: Milk Separator

**Goal:** Implement centrifugal separator — splits whole milk into cream and skim streams using mass balance.

**Files:**
- Create: `src/engine/separator.ts`
- Create: `tests/engine/separator.test.ts`

**Acceptance Criteria:**
- [ ] Cream stream hits target fat % within tolerance
- [ ] Skim stream has ~0.1% residual fat
- [ ] Fat in = fat out (cream + skim)
- [ ] SNF in = SNF out
- [ ] Water in = water out

**Verify:** `npx vitest run tests/engine/separator.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests**

```typescript
// tests/engine/separator.test.ts
import { describe, it, expect } from 'vitest';
import { separate } from '../src/engine/separator';
import { createStream, validateStream } from '../src/engine/types';

describe('separator', () => {
  const wholeMilk = createStream(1000, 0.04, 0.09); // 4% fat, 9% SNF

  it('produces cream at target fat %', () => {
    const { cream, skim } = separate(wholeMilk, { targetCreamFatPercent: 40 });
    const creamFatPercent = (cream.fat / cream.volume) * 100;
    expect(creamFatPercent).toBeCloseTo(40, 0);
  });

  it('produces skim with ~0.1% fat', () => {
    const { cream, skim } = separate(wholeMilk, { targetCreamFatPercent: 40 });
    const skimFatPercent = (skim.fat / skim.volume) * 100;
    expect(skimFatPercent).toBeCloseTo(0.1, 1);
  });

  it('conserves fat', () => {
    const { cream, skim } = separate(wholeMilk, { targetCreamFatPercent: 40 });
    expect(cream.fat + skim.fat).toBeCloseTo(wholeMilk.fat, 6);
  });

  it('conserves SNF', () => {
    const { cream, skim } = separate(wholeMilk, { targetCreamFatPercent: 40 });
    expect(cream.snf + skim.snf).toBeCloseTo(wholeMilk.snf, 6);
  });

  it('conserves water', () => {
    const { cream, skim } = separate(wholeMilk, { targetCreamFatPercent: 40 });
    expect(cream.water + skim.water).toBeCloseTo(wholeMilk.water, 6);
  });

  it('both streams validate', () => {
    const { cream, skim } = separate(wholeMilk, { targetCreamFatPercent: 40 });
    expect(validateStream(cream)).toBe(true);
    expect(validateStream(skim)).toBe(true);
  });

  it('higher target fat % means less cream volume', () => {
    const low = separate(wholeMilk, { targetCreamFatPercent: 35 });
    const high = separate(wholeMilk, { targetCreamFatPercent: 42 });
    expect(high.cream.volume).toBeLessThan(low.cream.volume);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
npx vitest run tests/engine/separator.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// src/engine/separator.ts
import { Stream, SeparatorConfig } from './types';

const SKIM_FAT_FRACTION = 0.001; // 0.1% residual fat in skim

export function separate(
  milk: Stream,
  config: SeparatorConfig,
): { cream: Stream; skim: Stream } {
  const f_m = milk.fat / milk.volume;       // milk fat fraction
  const f_c = config.targetCreamFatPercent / 100; // target cream fat fraction
  const f_s = SKIM_FAT_FRACTION;

  // Mass balance: cream volume
  const creamVolume = milk.volume * (f_m - f_s) / (f_c - f_s);
  const skimVolume = milk.volume - creamVolume;

  // Fat distribution
  const creamFat = creamVolume * f_c;
  const skimFat = milk.fat - creamFat;

  // SNF and water distribute proportionally to volume
  const creamFraction = creamVolume / milk.volume;
  const creamSnf = milk.snf * creamFraction;
  const skimSnf = milk.snf - creamSnf;
  const creamWater = creamVolume - creamFat - creamSnf;
  const skimWater = skimVolume - skimFat - skimSnf;

  return {
    cream: { volume: creamVolume, fat: creamFat, snf: creamSnf, water: creamWater },
    skim: { volume: skimVolume, fat: skimFat, snf: skimSnf, water: skimWater },
  };
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npx vitest run tests/engine/separator.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/separator.ts tests/engine/separator.test.ts
git commit -m "feat: add milk separator with mass balance"
```

---

### Task 4: Cheese Plant

**Goal:** Implement cheese plant — standardizes milk, calculates cheese yield via Van Slyke, outputs cheese + whey + excess cream.

**Files:**
- Create: `src/engine/cheese-plant.ts`
- Create: `tests/engine/cheese-plant.test.ts`

**Acceptance Criteria:**
- [ ] Cheese output matches expected yield for each cheese type
- [ ] Excess cream is sent when milk has more fat than needed for target casein:fat ratio
- [ ] Whey = input - cheese - excess cream (mass balance)
- [ ] All output streams validate

**Verify:** `npx vitest run tests/engine/cheese-plant.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests**

```typescript
// tests/engine/cheese-plant.test.ts
import { describe, it, expect } from 'vitest';
import { processCheese, CHEESE_PARAMS } from '../src/engine/cheese-plant';
import { createStream, validateStream, CheeseType } from '../src/engine/types';

describe('cheese plant', () => {
  // Skim milk: 0.1% fat, 9.3% SNF (slightly concentrated after separation)
  const skim = createStream(900, 0.001, 0.093);

  it('produces cheddar with correct moisture', () => {
    const result = processCheese(skim, { cheeseType: CheeseType.Cheddar });
    const moisture = result.cheese.water / result.cheese.volume;
    expect(moisture).toBeCloseTo(0.37, 1);
  });

  it('conserves total mass', () => {
    const result = processCheese(skim, { cheeseType: CheeseType.Cheddar });
    const totalOut = result.cheese.volume + result.whey.volume + result.excessCream.volume;
    expect(totalOut).toBeCloseTo(skim.volume, 2);
  });

  it('conserves fat', () => {
    const result = processCheese(skim, { cheeseType: CheeseType.Cheddar });
    const fatOut = result.cheese.fat + result.whey.fat + result.excessCream.fat;
    expect(fatOut).toBeCloseTo(skim.fat, 4);
  });

  it('conserves SNF', () => {
    const result = processCheese(skim, { cheeseType: CheeseType.Cheddar });
    const snfOut = result.cheese.snf + result.whey.snf + result.excessCream.snf;
    expect(snfOut).toBeCloseTo(skim.snf, 4);
  });

  it('parmesan has lower moisture than mozzarella', () => {
    const parm = processCheese(skim, { cheeseType: CheeseType.Parmesan });
    const mozz = processCheese(skim, { cheeseType: CheeseType.Mozzarella });
    const parmMoisture = parm.cheese.water / parm.cheese.volume;
    const mozzMoisture = mozz.cheese.water / mozz.cheese.volume;
    expect(parmMoisture).toBeLessThan(mozzMoisture);
  });

  it('all output streams validate', () => {
    for (const type of Object.values(CheeseType)) {
      const result = processCheese(skim, { cheeseType: type });
      expect(validateStream(result.cheese)).toBe(true);
      expect(validateStream(result.whey)).toBe(true);
      expect(validateStream(result.excessCream)).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
npx vitest run tests/engine/cheese-plant.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// src/engine/cheese-plant.ts
import { Stream, CheesePlantConfig, CheeseType, EMPTY_STREAM } from './types';

export interface CheeseParams {
  moisture: number;       // fraction (e.g. 0.37 for cheddar)
  fatRecovery: number;    // fraction of input fat retained in cheese
  caseinFatRatio: number; // target casein:fat ratio in cheese milk
  caseinRecovery: number; // fraction of casein (from SNF) retained in cheese
}

// Approximate: casein is ~78% of protein, protein is ~38% of SNF → casein ≈ 29.6% of SNF
const CASEIN_FRACTION_OF_SNF = 0.296;

export const CHEESE_PARAMS: Record<CheeseType, CheeseParams> = {
  [CheeseType.Cheddar]:    { moisture: 0.37, fatRecovery: 0.90, caseinFatRatio: 0.68, caseinRecovery: 0.75 },
  [CheeseType.Mozzarella]: { moisture: 0.47, fatRecovery: 0.85, caseinFatRatio: 0.95, caseinRecovery: 0.75 },
  [CheeseType.Swiss]:      { moisture: 0.38, fatRecovery: 0.88, caseinFatRatio: 0.80, caseinRecovery: 0.75 },
  [CheeseType.Parmesan]:   { moisture: 0.30, fatRecovery: 0.88, caseinFatRatio: 1.20, caseinRecovery: 0.75 },
};

export function processCheese(
  milk: Stream,
  config: CheesePlantConfig,
): { cheese: Stream; whey: Stream; excessCream: Stream } {
  const params = CHEESE_PARAMS[config.cheeseType];

  // Standardization: determine how much fat to keep vs send to cream pool
  const casein = milk.snf * CASEIN_FRACTION_OF_SNF;
  const targetFat = casein / params.caseinFatRatio;
  const availableFat = milk.fat;
  const fatForCheese = Math.min(targetFat, availableFat);
  const excessFat = availableFat - fatForCheese;

  // Excess cream stream (fat that exceeds standardization target)
  const excessCream: Stream = excessFat > 0.001
    ? { volume: excessFat, fat: excessFat, snf: 0, water: 0 }
    : { ...EMPTY_STREAM };

  // Standardized milk (after removing excess cream)
  const stdMilkVolume = milk.volume - excessCream.volume;
  const stdMilkFat = fatForCheese;
  const stdMilkSnf = milk.snf;
  const stdMilkWater = milk.water;

  // Cheese yield via Van Slyke-style formula
  const recoveredFat = stdMilkFat * params.fatRecovery;
  const recoveredCasein = casein * params.caseinRecovery;
  const cheeseSolids = recoveredFat + recoveredCasein;
  const cheeseVolume = cheeseSolids / (1 - params.moisture);
  const cheeseWater = cheeseVolume - cheeseSolids;
  const cheeseFat = recoveredFat;
  const cheeseSnf = recoveredCasein;

  // Whey = standardized milk - cheese (mass balance)
  const wheyFat = stdMilkFat - cheeseFat;
  const wheySnf = stdMilkSnf - cheeseSnf;
  const wheyWater = stdMilkWater - cheeseWater;
  const wheyVolume = wheyFat + wheySnf + wheyWater;

  return {
    cheese: { volume: cheeseVolume, fat: cheeseFat, snf: cheeseSnf, water: cheeseWater },
    whey: { volume: wheyVolume, fat: wheyFat, snf: wheySnf, water: wheyWater },
    excessCream: excessCream,
  };
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npx vitest run tests/engine/cheese-plant.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/cheese-plant.ts tests/engine/cheese-plant.test.ts
git commit -m "feat: add cheese plant with standardization and Van Slyke yield"
```

---

### Task 5: Butter Plant

**Goal:** Implement butter plant — churns cream into butter + buttermilk, dries buttermilk into powder (NFDM, BMP, or WMP).

**Files:**
- Create: `src/engine/butter-plant.ts`
- Create: `tests/engine/butter-plant.test.ts`

**Acceptance Criteria:**
- [ ] Butter hits target fat %
- [ ] Buttermilk composition is correct (cream minus butter)
- [ ] Powder output reflects selected type (WMP has fat added back)
- [ ] Mass balance: cream in = butter + powder out

**Verify:** `npx vitest run tests/engine/butter-plant.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests**

```typescript
// tests/engine/butter-plant.test.ts
import { describe, it, expect } from 'vitest';
import { processButterPlant } from '../src/engine/butter-plant';
import { validateStream, PowderType } from '../src/engine/types';

describe('butter plant', () => {
  // Cream: 40% fat, 5% SNF, 55% water
  const cream = { volume: 100, fat: 40, snf: 5, water: 55 };

  it('produces butter at target fat %', () => {
    const result = processButterPlant(cream, { targetButterFatPercent: 82, powderType: PowderType.NFDM });
    const butterFatPercent = (result.butter.fat / result.butter.volume) * 100;
    expect(butterFatPercent).toBeCloseTo(82, 0);
  });

  it('conserves total mass', () => {
    const result = processButterPlant(cream, { targetButterFatPercent: 82, powderType: PowderType.NFDM });
    const totalOut = result.butter.volume + result.powder.volume;
    expect(totalOut).toBeCloseTo(cream.volume, 2);
  });

  it('conserves fat', () => {
    const result = processButterPlant(cream, { targetButterFatPercent: 82, powderType: PowderType.NFDM });
    expect(result.butter.fat + result.powder.fat).toBeCloseTo(cream.fat, 4);
  });

  it('NFDM powder has minimal fat', () => {
    const result = processButterPlant(cream, { targetButterFatPercent: 82, powderType: PowderType.NFDM });
    const powderFatPercent = (result.powder.fat / result.powder.volume) * 100;
    expect(powderFatPercent).toBeLessThan(2);
  });

  it('WMP powder has fat added back', () => {
    const result = processButterPlant(cream, { targetButterFatPercent: 82, powderType: PowderType.WMP });
    const powderFatPercent = (result.powder.fat / result.powder.volume) * 100;
    expect(powderFatPercent).toBeGreaterThan(20);
  });

  it('all streams validate', () => {
    for (const type of Object.values(PowderType)) {
      const result = processButterPlant(cream, { targetButterFatPercent: 82, powderType: type });
      expect(validateStream(result.butter)).toBe(true);
      expect(validateStream(result.powder)).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
npx vitest run tests/engine/butter-plant.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// src/engine/butter-plant.ts
import { Stream, ButterPlantConfig, PowderType } from './types';

// Butter: target fat %, ~1.5% SNF, rest is water
const BUTTER_SNF_FRACTION = 0.015;
// WMP target: ~26% fat, ~71% SNF, ~3% water (dry product)
const WMP_FAT_FRACTION = 0.26;
// BMP and NFDM: ~1% fat, ~96% SNF, ~3% water (dry products)
const DRY_POWDER_FAT_FRACTION = 0.01;
const DRY_POWDER_WATER_FRACTION = 0.03;

export function processButterPlant(
  cream: Stream,
  config: ButterPlantConfig,
): { butter: Stream; powder: Stream } {
  const butterFatFraction = config.targetButterFatPercent / 100;

  // Churning: most fat goes to butter, rest stays in buttermilk
  // Butter volume determined by fat available and target fat %
  const butterFat = cream.fat * 0.95; // 95% fat recovery in churning
  const butterVolume = butterFat / butterFatFraction;
  const butterSnf = butterVolume * BUTTER_SNF_FRACTION;
  const butterWater = butterVolume - butterFat - butterSnf;

  // Buttermilk = cream - butter
  const buttermilkFat = cream.fat - butterFat;
  const buttermilkSnf = cream.snf - butterSnf;
  const buttermilkWater = cream.water - butterWater;
  const buttermilkVolume = buttermilkFat + buttermilkSnf + buttermilkWater;

  // Drying buttermilk into powder
  let powder: Stream;

  if (config.powderType === PowderType.WMP) {
    // WMP: add fat back to buttermilk before drying
    // Total solids from buttermilk (SNF + fat) become part of WMP
    const powderSnf = buttermilkSnf;
    const targetPowderVolume = powderSnf / (1 - WMP_FAT_FRACTION - DRY_POWDER_WATER_FRACTION);
    const powderFat = targetPowderVolume * WMP_FAT_FRACTION;
    const powderWater = targetPowderVolume * DRY_POWDER_WATER_FRACTION;
    // Extra fat for WMP comes from the butter stream — adjust butter accordingly
    const extraFatNeeded = powderFat - buttermilkFat;
    if (extraFatNeeded > 0) {
      // Take fat from butter to enrich powder
      powder = { volume: targetPowderVolume, fat: powderFat, snf: powderSnf, water: powderWater };
      // Adjust butter: less fat
      const adjButterFat = butterFat - extraFatNeeded;
      const adjButterVolume = adjButterFat / butterFatFraction;
      const adjButterSnf = adjButterVolume * BUTTER_SNF_FRACTION;
      const adjButterWater = adjButterVolume - adjButterFat - adjButterSnf;
      return {
        butter: { volume: adjButterVolume, fat: adjButterFat, snf: adjButterSnf, water: adjButterWater },
        powder,
      };
    }
    powder = { volume: buttermilkVolume, fat: buttermilkFat, snf: powderSnf, water: buttermilkWater };
  } else {
    // NFDM or BMP: dry the buttermilk, remove most water
    // Both are essentially dried buttermilk — BMP is marketed differently but same process
    const powderSnf = buttermilkSnf;
    const powderFat = buttermilkFat; // minimal fat remains
    const totalSolids = powderSnf + powderFat;
    const powderVolume = totalSolids / (1 - DRY_POWDER_WATER_FRACTION);
    const powderWater = powderVolume * DRY_POWDER_WATER_FRACTION;
    powder = { volume: powderVolume, fat: powderFat, snf: powderSnf, water: powderWater };
  }

  return {
    butter: { volume: butterVolume, fat: butterFat, snf: butterSnf, water: butterWater },
    powder,
  };
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npx vitest run tests/engine/butter-plant.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/butter-plant.ts tests/engine/butter-plant.test.ts
git commit -m "feat: add butter plant with churning and powder drying"
```

---

### Task 6: Market Pricing

**Goal:** Implement supply/demand pricing model — each product has base price, demand, elasticity.

**Files:**
- Create: `src/engine/market.ts`
- Create: `tests/engine/market.test.ts`

**Acceptance Criteria:**
- [ ] Price increases when supply < demand
- [ ] Price decreases when supply > demand
- [ ] Elasticity controls sensitivity
- [ ] Revenue calculated correctly

**Verify:** `npx vitest run tests/engine/market.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests**

```typescript
// tests/engine/market.test.ts
import { describe, it, expect } from 'vitest';
import { calculatePrices, calculateRevenue, DEFAULT_MARKET } from '../src/engine/market';

describe('market', () => {
  it('returns base price when supply equals demand', () => {
    const supply = { butter: 100, nfdm: 50, bmp: 0, wmp: 0, cheddar: 80, mozzarella: 0, swiss: 0, parmesan: 0, whey: 200 };
    // Set demand equal to supply
    const market = { ...DEFAULT_MARKET };
    for (const key of Object.keys(supply) as Array<keyof typeof supply>) {
      market[key] = { ...market[key], demand: supply[key] };
    }
    const prices = calculatePrices(supply, market);
    expect(prices.butter).toBeCloseTo(market.butter.basePrice, 1);
  });

  it('price rises when supply is below demand', () => {
    const supply = { butter: 50, nfdm: 0, bmp: 0, wmp: 0, cheddar: 0, mozzarella: 0, swiss: 0, parmesan: 0, whey: 0 };
    const prices = calculatePrices(supply, DEFAULT_MARKET);
    expect(prices.butter).toBeGreaterThan(DEFAULT_MARKET.butter.basePrice);
  });

  it('price falls when supply exceeds demand', () => {
    const supply = { butter: 10000, nfdm: 0, bmp: 0, wmp: 0, cheddar: 0, mozzarella: 0, swiss: 0, parmesan: 0, whey: 0 };
    const prices = calculatePrices(supply, DEFAULT_MARKET);
    expect(prices.butter).toBeLessThan(DEFAULT_MARKET.butter.basePrice);
  });

  it('calculates revenue correctly', () => {
    const supply = { butter: 100, nfdm: 0, bmp: 0, wmp: 0, cheddar: 0, mozzarella: 0, swiss: 0, parmesan: 0, whey: 0 };
    const prices = { butter: 2.50, nfdm: 0, bmp: 0, wmp: 0, cheddar: 0, mozzarella: 0, swiss: 0, parmesan: 0, whey: 0 };
    expect(calculateRevenue(supply, prices)).toBeCloseTo(250);
  });

  it('zero supply returns base price (no division by zero)', () => {
    const supply = { butter: 0, nfdm: 0, bmp: 0, wmp: 0, cheddar: 0, mozzarella: 0, swiss: 0, parmesan: 0, whey: 0 };
    const prices = calculatePrices(supply, DEFAULT_MARKET);
    expect(prices.butter).toBe(DEFAULT_MARKET.butter.basePrice);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
npx vitest run tests/engine/market.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// src/engine/market.ts
import { ProductVolumes, ProductPrices } from './types';

export interface MarketParams {
  basePrice: number;   // $/lb
  demand: number;      // lbs per tick
  elasticity: number;  // price sensitivity (0.1 = gentle, 1.0 = aggressive)
}

export type MarketConfig = Record<keyof ProductVolumes, MarketParams>;

export const DEFAULT_MARKET: MarketConfig = {
  butter:     { basePrice: 2.50, demand: 100, elasticity: 0.3 },
  nfdm:       { basePrice: 1.20, demand: 80,  elasticity: 0.3 },
  bmp:        { basePrice: 1.40, demand: 30,  elasticity: 0.3 },
  wmp:        { basePrice: 1.80, demand: 50,  elasticity: 0.3 },
  cheddar:    { basePrice: 1.80, demand: 120, elasticity: 0.3 },
  mozzarella: { basePrice: 1.90, demand: 100, elasticity: 0.3 },
  swiss:      { basePrice: 2.20, demand: 40,  elasticity: 0.3 },
  parmesan:   { basePrice: 3.50, demand: 30,  elasticity: 0.3 },
  whey:       { basePrice: 0.40, demand: 200, elasticity: 0.2 },
};

export function calculatePrices(supply: ProductVolumes, market: MarketConfig): ProductPrices {
  const prices = {} as ProductPrices;
  for (const key of Object.keys(market) as Array<keyof ProductVolumes>) {
    const { basePrice, demand, elasticity } = market[key];
    if (supply[key] <= 0) {
      prices[key] = basePrice;
    } else {
      prices[key] = basePrice * Math.pow(demand / supply[key], elasticity);
    }
  }
  return prices;
}

export function calculateRevenue(supply: ProductVolumes, prices: ProductPrices): number {
  let revenue = 0;
  for (const key of Object.keys(supply) as Array<keyof ProductVolumes>) {
    revenue += supply[key] * prices[key];
  }
  return revenue;
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npx vitest run tests/engine/market.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/market.ts tests/engine/market.test.ts
git commit -m "feat: add supply/demand market pricing model"
```

---

### Task 7: Simulation Tick Orchestrator

**Goal:** Wire all engine nodes together into a single `tick()` function that takes config and returns full simulation state.

**Files:**
- Create: `src/engine/simulation.ts`
- Create: `tests/engine/simulation.test.ts`

**Acceptance Criteria:**
- [ ] `tick()` produces complete `SimulationState` from `SimulationConfig`
- [ ] Cream pool correctly aggregates separator cream + cheese excess cream
- [ ] Skim split routes correctly to cheese plants A/B
- [ ] Cream split routes correctly to butter plants A/B
- [ ] Mass balance error is near zero across the whole system
- [ ] Production volumes map to correct product names based on cheese type and powder type

**Verify:** `npx vitest run tests/engine/simulation.test.ts` → PASS

**Steps:**

- [ ] **Step 1: Write tests**

```typescript
// tests/engine/simulation.test.ts
import { describe, it, expect } from 'vitest';
import { tick, DEFAULT_CONFIG } from '../src/engine/simulation';
import { CheeseType, PowderType } from '../src/engine/types';

describe('simulation tick', () => {
  it('produces a complete state', () => {
    const state = tick(DEFAULT_CONFIG, 0);
    expect(state.tick).toBe(0);
    expect(state.nodes.wholeMilk.volume).toBeGreaterThan(0);
    expect(state.revenue).toBeGreaterThan(0);
  });

  it('mass balance error is near zero', () => {
    const state = tick(DEFAULT_CONFIG, 0);
    expect(Math.abs(state.massBalanceError.fat)).toBeLessThan(0.01);
    expect(Math.abs(state.massBalanceError.snf)).toBeLessThan(0.01);
    expect(Math.abs(state.massBalanceError.water)).toBeLessThan(1);
  });

  it('cream pool includes separator cream and cheese excess cream', () => {
    const state = tick(DEFAULT_CONFIG, 0);
    const expectedCreamPoolFat = state.nodes.cream.fat
      + state.nodes.cheesePlantA.excessCream.fat
      + state.nodes.cheesePlantB.excessCream.fat;
    expect(state.nodes.creamPool.fat).toBeCloseTo(expectedCreamPoolFat, 4);
  });

  it('skim splits correctly between cheese plants', () => {
    const config = { ...DEFAULT_CONFIG, skimSplitPercent: 60 };
    const state = tick(config, 0);
    const totalSkimToPlants = state.nodes.cheesePlantA.cheese.volume
      + state.nodes.cheesePlantA.whey.volume
      + state.nodes.cheesePlantA.excessCream.volume
      + state.nodes.cheesePlantB.cheese.volume
      + state.nodes.cheesePlantB.whey.volume
      + state.nodes.cheesePlantB.excessCream.volume;
    expect(totalSkimToPlants).toBeCloseTo(state.nodes.skim.volume, 1);
  });

  it('production volumes reflect cheese types', () => {
    const config = {
      ...DEFAULT_CONFIG,
      cheesePlantA: { cheeseType: CheeseType.Cheddar },
      cheesePlantB: { cheeseType: CheeseType.Mozzarella },
    };
    const state = tick(config, 0);
    expect(state.production.cheddar).toBeGreaterThan(0);
    expect(state.production.mozzarella).toBeGreaterThan(0);
    expect(state.production.swiss).toBe(0);
    expect(state.production.parmesan).toBe(0);
  });

  it('changing config changes output', () => {
    const state1 = tick(DEFAULT_CONFIG, 0);
    const highFatConfig = {
      ...DEFAULT_CONFIG,
      producer: { ...DEFAULT_CONFIG.producer, fatPercent: 5.0 },
    };
    const state2 = tick(highFatConfig, 1);
    expect(state2.nodes.cream.fat).toBeGreaterThan(state1.nodes.cream.fat);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
npx vitest run tests/engine/simulation.test.ts
```

- [ ] **Step 3: Implement**

```typescript
// src/engine/simulation.ts
import {
  SimulationConfig, SimulationState, ProductVolumes, Stream,
  CheeseType, PowderType, addStreams, EMPTY_STREAM,
} from './types';
import { produce } from './producer';
import { separate } from './separator';
import { processCheese } from './cheese-plant';
import { processButterPlant } from './butter-plant';
import { calculatePrices, calculateRevenue, DEFAULT_MARKET } from './market';

export const DEFAULT_CONFIG: SimulationConfig = {
  producer: { fatPercent: 4.0, snfPercent: 9.0, productionRate: 1000 },
  separator: { targetCreamFatPercent: 40 },
  skimSplitPercent: 50,
  creamSplitPercent: 50,
  butterPlantA: { targetButterFatPercent: 82, powderType: PowderType.NFDM },
  butterPlantB: { targetButterFatPercent: 80, powderType: PowderType.BMP },
  cheesePlantA: { cheeseType: CheeseType.Cheddar },
  cheesePlantB: { cheeseType: CheeseType.Mozzarella },
};

function splitStream(stream: Stream, fractionA: number): [Stream, Stream] {
  const fractionB = 1 - fractionA;
  return [
    { volume: stream.volume * fractionA, fat: stream.fat * fractionA, snf: stream.snf * fractionA, water: stream.water * fractionA },
    { volume: stream.volume * fractionB, fat: stream.fat * fractionB, snf: stream.snf * fractionB, water: stream.water * fractionB },
  ];
}

function mapCheeseToProduct(cheeseType: CheeseType, volume: number): Partial<ProductVolumes> {
  return { [cheeseType]: volume };
}

function mapPowderToProduct(powderType: PowderType, volume: number): Partial<ProductVolumes> {
  return { [powderType]: volume };
}

export function tick(config: SimulationConfig, tickNum: number): SimulationState {
  // 1. Produce milk
  const wholeMilk = produce(config.producer);

  // 2. Separate
  const { cream: separatorCream, skim } = separate(wholeMilk, config.separator);

  // 3. Split skim to cheese plants
  const [skimA, skimB] = splitStream(skim, config.skimSplitPercent / 100);

  // 4. Cheese plants
  const cheeseA = processCheese(skimA, config.cheesePlantA);
  const cheeseB = processCheese(skimB, config.cheesePlantB);

  // 5. Cream pool: separator cream + cheese excess cream
  const creamPool = addStreams(separatorCream, cheeseA.excessCream, cheeseB.excessCream);

  // 6. Split cream pool to butter plants
  const [creamForA, creamForB] = splitStream(creamPool, config.creamSplitPercent / 100);

  // 7. Butter plants
  const butterA = processButterPlant(creamForA, config.butterPlantA);
  const butterB = processButterPlant(creamForB, config.butterPlantB);

  // 8. Aggregate production volumes
  const production: ProductVolumes = {
    butter: butterA.butter.volume + butterB.butter.volume,
    nfdm: 0, bmp: 0, wmp: 0,
    cheddar: 0, mozzarella: 0, swiss: 0, parmesan: 0,
    whey: cheeseA.whey.volume + cheeseB.whey.volume,
  };

  // Map cheese volumes to product names
  production[config.cheesePlantA.cheeseType] += cheeseA.cheese.volume;
  production[config.cheesePlantB.cheeseType] += cheeseB.cheese.volume;

  // Map powder volumes to product names
  production[config.butterPlantA.powderType] += butterA.powder.volume;
  production[config.butterPlantB.powderType] += butterB.powder.volume;

  // 9. Market pricing
  const prices = calculatePrices(production, DEFAULT_MARKET);
  const revenue = calculateRevenue(production, prices);

  // 10. Mass balance audit
  const totalIn = wholeMilk;
  const totalOut = addStreams(
    cheeseA.cheese, cheeseB.cheese,
    cheeseA.whey, cheeseB.whey,
    butterA.butter, butterB.butter,
    butterA.powder, butterB.powder,
  );
  const massBalanceError = {
    fat: totalIn.fat - totalOut.fat,
    snf: totalIn.snf - totalOut.snf,
    water: totalIn.water - totalOut.water,
  };

  return {
    tick: tickNum,
    config,
    nodes: {
      wholeMilk,
      cream: separatorCream,
      skim,
      cheesePlantA: cheeseA,
      cheesePlantB: cheeseB,
      creamPool,
      butterPlantA: butterA,
      butterPlantB: butterB,
    },
    production,
    prices,
    revenue,
    massBalanceError,
  };
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
npx vitest run tests/engine/simulation.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/simulation.ts tests/engine/simulation.test.ts
git commit -m "feat: add simulation tick orchestrator wiring all engine nodes"
```

---

### Task 8: UI — App Shell and Controls

**Goal:** Build the main App component with simulation loop and the Controls panel with all sliders/dropdowns.

**Files:**
- Create: `src/ui/App.tsx`
- Create: `src/ui/Controls.tsx`
- Modify: `src/main.tsx` — import App from ui/App
- Modify: `src/index.css` — dashboard layout styles

**Acceptance Criteria:**
- [ ] App renders with left (controls) and right (dashboard) panels
- [ ] Simulation runs on play, pauses on pause
- [ ] All config parameters have working controls
- [ ] Changing a control updates config for next tick

**Verify:** `npm run dev -- --host 0.0.0.0` → open in browser, controls render and simulation ticks

**Steps:**

- [ ] **Step 1: Create Controls component**

```tsx
// src/ui/Controls.tsx
import { SimulationConfig, CheeseType, PowderType } from '@engine/types';

interface ControlsProps {
  config: SimulationConfig;
  onChange: (config: SimulationConfig) => void;
  running: boolean;
  onToggleRun: () => void;
  ticksPerSecond: number;
  onTicksPerSecondChange: (tps: number) => void;
}

export function Controls({ config, onChange, running, onToggleRun, ticksPerSecond, onTicksPerSecondChange }: ControlsProps) {
  const update = (path: string, value: number | string) => {
    const next = structuredClone(config);
    const parts = path.split('.');
    let obj: any = next;
    for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
    obj[parts[parts.length - 1]] = value;
    onChange(next);
  };

  return (
    <div className="controls">
      <h2>Controls</h2>

      <button className="play-btn" onClick={onToggleRun}>
        {running ? '⏸ Pause' : '▶ Play'}
      </button>

      <label>
        Speed: {ticksPerSecond} ticks/sec
        <input type="range" min={1} max={60} value={ticksPerSecond}
          onChange={e => onTicksPerSecondChange(Number(e.target.value))} />
      </label>

      <fieldset>
        <legend>Milk Producer</legend>
        <label>
          Fat %: {config.producer.fatPercent.toFixed(1)}
          <input type="range" min={3.0} max={5.0} step={0.1} value={config.producer.fatPercent}
            onChange={e => update('producer.fatPercent', Number(e.target.value))} />
        </label>
        <label>
          SNF %: {config.producer.snfPercent.toFixed(1)}
          <input type="range" min={7.5} max={9.5} step={0.1} value={config.producer.snfPercent}
            onChange={e => update('producer.snfPercent', Number(e.target.value))} />
        </label>
        <label>
          Production: {config.producer.productionRate} lbs/tick
          <input type="range" min={100} max={5000} step={100} value={config.producer.productionRate}
            onChange={e => update('producer.productionRate', Number(e.target.value))} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Separator</legend>
        <label>
          Cream Fat %: {config.separator.targetCreamFatPercent}
          <input type="range" min={30} max={45} step={1} value={config.separator.targetCreamFatPercent}
            onChange={e => update('separator.targetCreamFatPercent', Number(e.target.value))} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Routing</legend>
        <label>
          Skim → Cheese A: {config.skimSplitPercent}%
          <input type="range" min={0} max={100} step={5} value={config.skimSplitPercent}
            onChange={e => update('skimSplitPercent', Number(e.target.value))} />
        </label>
        <label>
          Cream → Butter A: {config.creamSplitPercent}%
          <input type="range" min={0} max={100} step={5} value={config.creamSplitPercent}
            onChange={e => update('creamSplitPercent', Number(e.target.value))} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Butter Plant A</legend>
        <label>
          Butter Fat %: {config.butterPlantA.targetButterFatPercent}
          <input type="range" min={78} max={84} step={1} value={config.butterPlantA.targetButterFatPercent}
            onChange={e => update('butterPlantA.targetButterFatPercent', Number(e.target.value))} />
        </label>
        <label>
          Powder Type:
          <select value={config.butterPlantA.powderType}
            onChange={e => update('butterPlantA.powderType', e.target.value)}>
            {Object.values(PowderType).map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Butter Plant B</legend>
        <label>
          Butter Fat %: {config.butterPlantB.targetButterFatPercent}
          <input type="range" min={78} max={84} step={1} value={config.butterPlantB.targetButterFatPercent}
            onChange={e => update('butterPlantB.targetButterFatPercent', Number(e.target.value))} />
        </label>
        <label>
          Powder Type:
          <select value={config.butterPlantB.powderType}
            onChange={e => update('butterPlantB.powderType', e.target.value)}>
            {Object.values(PowderType).map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Cheese Plant A</legend>
        <label>
          Cheese Type:
          <select value={config.cheesePlantA.cheeseType}
            onChange={e => update('cheesePlantA.cheeseType', e.target.value)}>
            {Object.values(CheeseType).map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Cheese Plant B</legend>
        <label>
          Cheese Type:
          <select value={config.cheesePlantB.cheeseType}
            onChange={e => update('cheesePlantB.cheeseType', e.target.value)}>
            {Object.values(CheeseType).map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select>
        </label>
      </fieldset>
    </div>
  );
}
```

- [ ] **Step 2: Create App component with simulation loop**

```tsx
// src/ui/App.tsx
import { useState, useRef, useCallback, useEffect } from 'react';
import { SimulationConfig, SimulationState } from '@engine/types';
import { tick, DEFAULT_CONFIG } from '@engine/simulation';
import { Controls } from './Controls';

export function App() {
  const [config, setConfig] = useState<SimulationConfig>(DEFAULT_CONFIG);
  const [state, setState] = useState<SimulationState>(() => tick(DEFAULT_CONFIG, 0));
  const [running, setRunning] = useState(false);
  const [ticksPerSecond, setTicksPerSecond] = useState(10);
  const tickRef = useRef(0);
  const configRef = useRef(config);
  configRef.current = config;

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => {
      tickRef.current += 1;
      const newState = tick(configRef.current, tickRef.current);
      setState(newState);
    }, 1000 / ticksPerSecond);
    return () => clearInterval(interval);
  }, [running, ticksPerSecond]);

  return (
    <div className="app">
      <Controls
        config={config}
        onChange={setConfig}
        running={running}
        onToggleRun={() => setRunning(r => !r)}
        ticksPerSecond={ticksPerSecond}
        onTicksPerSecondChange={setTicksPerSecond}
      />
      <div className="dashboard">
        <h2>Dashboard</h2>
        <div className="tick-counter">Tick: {state.tick}</div>
        <div className="placeholder-panels">
          <div className="panel">Flow Diagram (Task 9)</div>
          <div className="panel">Production (Task 10)</div>
          <div className="panel">Prices (Task 10)</div>
          <div className="panel">Mass Balance (Task 10)</div>
          <div className="panel">Revenue: ${state.revenue.toFixed(2)}/tick</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update main.tsx**

```tsx
// src/main.tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './ui/App';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 4: Add dashboard styles to index.css**

```css
/* src/index.css */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; background: #1a1a2e; color: #e0e0e0; }
#root { width: 100vw; height: 100vh; }

.app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.controls {
  width: 320px;
  min-width: 320px;
  padding: 16px;
  overflow-y: auto;
  background: #16213e;
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.controls h2 { margin-bottom: 8px; color: #7db8df; }

.controls fieldset {
  border: 1px solid #333;
  border-radius: 6px;
  padding: 10px;
}

.controls legend {
  color: #aaa;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.controls label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  margin-bottom: 8px;
}

.controls input[type="range"] { width: 100%; }

.controls select {
  background: #1a1a2e;
  color: #e0e0e0;
  border: 1px solid #444;
  padding: 4px;
  border-radius: 4px;
}

.play-btn {
  background: #2a6a4a;
  color: white;
  border: none;
  padding: 10px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
}
.play-btn:hover { background: #3a8a5a; }

.dashboard {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dashboard h2 { color: #7db8df; }

.tick-counter {
  font-size: 14px;
  color: #888;
}

.placeholder-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
}

.panel {
  background: #16213e;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 14px;
}
```

- [ ] **Step 5: Verify dev server works and commit**

```bash
npm run dev -- --host 0.0.0.0 &
sleep 3
curl -s http://localhost:5173 | grep -o 'Moomoo'
kill %1
git add src/ui/App.tsx src/ui/Controls.tsx src/main.tsx src/index.css
git commit -m "feat: add App shell with controls panel and simulation loop"
```

---

### Task 9: UI — Flow Diagram

**Goal:** Build an SVG-based flow diagram showing all processing nodes with live stream numbers (volumes, fat%, SNF%).

**Files:**
- Create: `src/ui/FlowDiagram.tsx`
- Modify: `src/ui/App.tsx` — replace placeholder with FlowDiagram component

**Acceptance Criteria:**
- [ ] Shows all nodes: Producer, Separator, Cheese A/B, Cream Pool, Butter A/B
- [ ] Stream lines connect nodes with live volume and composition labels
- [ ] Numbers update each tick
- [ ] Cream recirculation from cheese to cream pool is visible

**Verify:** Visual — open in browser, play simulation, numbers update on diagram

**Steps:**

- [ ] **Step 1: Create FlowDiagram component**

```tsx
// src/ui/FlowDiagram.tsx
import { NodeOutputs, Stream } from '@engine/types';

interface FlowDiagramProps {
  nodes: NodeOutputs;
}

function fmt(n: number): string {
  return n < 10 ? n.toFixed(2) : n.toFixed(0);
}

function pct(part: number, total: number): string {
  if (total === 0) return '0%';
  return ((part / total) * 100).toFixed(1) + '%';
}

function StreamLabel({ stream, x, y }: { stream: Stream; x: number; y: number }) {
  return (
    <text x={x} y={y} fill="#aaa" fontSize="10" textAnchor="middle">
      <tspan x={x} dy="0">{fmt(stream.volume)} lbs</tspan>
      <tspan x={x} dy="12">F:{pct(stream.fat, stream.volume)} S:{pct(stream.snf, stream.volume)}</tspan>
    </text>
  );
}

function Node({ x, y, w, h, label, color }: { x: number; y: number; w: number; h: number; label: string; color: string }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={6} fill="none" stroke={color} strokeWidth={2} />
      <text x={x + w / 2} y={y + h / 2 + 4} fill={color} fontSize="12" textAnchor="middle" fontWeight="bold">{label}</text>
    </g>
  );
}

export function FlowDiagram({ nodes }: FlowDiagramProps) {
  return (
    <svg viewBox="0 0 700 520" style={{ width: '100%', height: '100%', minHeight: 400 }}>
      {/* Producer */}
      <Node x={275} y={10} w={150} h={36} label="Milk Producer" color="#7ddf7d" />
      <StreamLabel stream={nodes.wholeMilk} x={350} y={60} />
      <line x1={350} y1={46} x2={350} y2={85} stroke="#555" strokeWidth={1} />

      {/* Separator */}
      <Node x={275} y={85} w={150} h={36} label="Separator" color="#7db8df" />

      {/* Skim line (right) */}
      <line x1={425} y1={103} x2={530} y2={103} stroke="#555" />
      <line x1={530} y1={103} x2={530} y2={180} stroke="#555" />
      <StreamLabel stream={nodes.skim} x={530} y={140} />

      {/* Cream line (left) */}
      <line x1={275} y1={103} x2={170} y2={103} stroke="#555" />
      <line x1={170} y1={103} x2={170} y2={310} stroke="#555" />
      <StreamLabel stream={nodes.cream} x={170} y={140} />

      {/* Cheese Plants */}
      <Node x={440} y={180} w={120} h={36} label="Cheese A" color="#df7d7d" />
      <Node x={570} y={180} w={120} h={36} label="Cheese B" color="#df7d7d" />

      {/* Cheese outputs */}
      <StreamLabel stream={nodes.cheesePlantA.cheese} x={500} y={240} />
      <text x={500} y={262} fill="#df7d7d" fontSize="9" textAnchor="middle">cheese+whey</text>

      <StreamLabel stream={nodes.cheesePlantB.cheese} x={630} y={240} />
      <text x={630} y={262} fill="#df7d7d" fontSize="9" textAnchor="middle">cheese+whey</text>

      {/* Excess cream arrows back to cream pool */}
      <line x1={440} y1={216} x2={320} y2={310} stroke="#dfbf5f" strokeDasharray="4" />
      <line x1={570} y1={216} x2={320} y2={310} stroke="#dfbf5f" strokeDasharray="4" />
      <text x={370} y={275} fill="#dfbf5f" fontSize="9" textAnchor="middle">excess cream</text>

      {/* Cream Pool */}
      <Node x={110} y={310} w={150} h={36} label="Cream Pool" color="#dfbf5f" />
      <StreamLabel stream={nodes.creamPool} x={185} y={365} />

      {/* Butter Plants */}
      <line x1={145} y1={346} x2={100} y2={400} stroke="#555" />
      <line x1={225} y1={346} x2={270} y2={400} stroke="#555" />

      <Node x={30} y={400} w={130} h={36} label="Butter A" color="#dfbf5f" />
      <Node x={200} y={400} w={130} h={36} label="Butter B" color="#dfbf5f" />

      {/* Butter outputs */}
      <StreamLabel stream={nodes.butterPlantA.butter} x={95} y={460} />
      <text x={95} y={482} fill="#dfbf5f" fontSize="9" textAnchor="middle">butter+powder</text>

      <StreamLabel stream={nodes.butterPlantB.butter} x={265} y={460} />
      <text x={265} y={482} fill="#dfbf5f" fontSize="9" textAnchor="middle">butter+powder</text>
    </svg>
  );
}
```

- [ ] **Step 2: Wire into App.tsx — replace the Flow Diagram placeholder**

In `src/ui/App.tsx`, add the import:
```tsx
import { FlowDiagram } from './FlowDiagram';
```

Replace `<div className="panel">Flow Diagram (Task 9)</div>` with:
```tsx
<div className="panel flow-panel">
  <FlowDiagram nodes={state.nodes} />
</div>
```

- [ ] **Step 3: Add flow panel style to index.css**

```css
.flow-panel {
  grid-column: 1 / -1;
  min-height: 400px;
}
```

- [ ] **Step 4: Verify visually and commit**

```bash
git add src/ui/FlowDiagram.tsx src/ui/App.tsx src/index.css
git commit -m "feat: add SVG flow diagram with live stream numbers"
```

---

### Task 10: UI — Dashboard Panels (Production, Prices, Mass Balance, Revenue)

**Goal:** Build the remaining dashboard panels — production bar chart, price tickers, mass balance audit table, and revenue breakdown.

**Files:**
- Create: `src/ui/ProductionChart.tsx`
- Create: `src/ui/PriceTicker.tsx`
- Create: `src/ui/MassBalance.tsx`
- Create: `src/ui/Revenue.tsx`
- Modify: `src/ui/App.tsx` — wire in all panels, add price history tracking

**Acceptance Criteria:**
- [ ] Production panel shows bar chart of all product volumes
- [ ] Price panel shows current price per product with recent trend (sparkline or arrow)
- [ ] Mass balance panel shows fat/SNF/water in vs out with error highlighted
- [ ] Revenue panel shows total and per-product breakdown
- [ ] All update each tick

**Verify:** Visual — open in browser, play simulation, all panels updating

**Steps:**

- [ ] **Step 1: Create ProductionChart (CSS bar chart)**

```tsx
// src/ui/ProductionChart.tsx
import { ProductVolumes } from '@engine/types';

interface ProductionChartProps {
  production: ProductVolumes;
}

const COLORS: Record<string, string> = {
  butter: '#dfbf5f', nfdm: '#8ab4f8', bmp: '#a8d8ea', wmp: '#f8d8a8',
  cheddar: '#df7d7d', mozzarella: '#e8a87c', swiss: '#d4a574', parmesan: '#c49a6c',
  whey: '#88c999',
};

export function ProductionChart({ production }: ProductionChartProps) {
  const entries = Object.entries(production).filter(([, v]) => v > 0);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="production-chart">
      <h3>Production (lbs/tick)</h3>
      {entries.map(([name, vol]) => (
        <div key={name} className="bar-row">
          <span className="bar-label">{name}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(vol / max) * 100}%`, background: COLORS[name] || '#888' }} />
          </div>
          <span className="bar-value">{vol.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create PriceTicker**

```tsx
// src/ui/PriceTicker.tsx
import { ProductPrices } from '@engine/types';

interface PriceTickerProps {
  prices: ProductPrices;
  previousPrices: ProductPrices | null;
}

export function PriceTicker({ prices, previousPrices }: PriceTickerProps) {
  const entries = Object.entries(prices) as Array<[keyof ProductPrices, number]>;

  return (
    <div className="price-ticker">
      <h3>Prices ($/lb)</h3>
      <div className="price-grid">
        {entries.map(([name, price]) => {
          const prev = previousPrices ? previousPrices[name] : price;
          const delta = price - prev;
          const arrow = delta > 0.001 ? '▲' : delta < -0.001 ? '▼' : '—';
          const color = delta > 0.001 ? '#4caf50' : delta < -0.001 ? '#f44336' : '#888';
          return (
            <div key={name} className="price-item">
              <span className="price-name">{name}</span>
              <span className="price-value">${price.toFixed(3)}</span>
              <span style={{ color }}>{arrow}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create MassBalance**

```tsx
// src/ui/MassBalance.tsx

interface MassBalanceProps {
  input: { fat: number; snf: number; water: number };
  error: { fat: number; snf: number; water: number };
}

export function MassBalance({ input, error }: MassBalanceProps) {
  const rows = [
    { name: 'Fat', inVal: input.fat, err: error.fat },
    { name: 'SNF', inVal: input.snf, err: error.snf },
    { name: 'Water', inVal: input.water, err: error.water },
  ];

  return (
    <div className="mass-balance">
      <h3>Mass Balance Audit</h3>
      <table>
        <thead>
          <tr><th>Component</th><th>In (lbs)</th><th>Error (lbs)</th><th>Error %</th></tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const errPct = r.inVal > 0 ? (Math.abs(r.err) / r.inVal) * 100 : 0;
            const isOk = errPct < 0.1;
            return (
              <tr key={r.name}>
                <td>{r.name}</td>
                <td>{r.inVal.toFixed(2)}</td>
                <td style={{ color: isOk ? '#4caf50' : '#f44336' }}>{r.err.toFixed(4)}</td>
                <td style={{ color: isOk ? '#4caf50' : '#f44336' }}>{errPct.toFixed(3)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Create Revenue**

```tsx
// src/ui/Revenue.tsx
import { ProductVolumes, ProductPrices } from '@engine/types';

interface RevenueProps {
  production: ProductVolumes;
  prices: ProductPrices;
  totalRevenue: number;
}

export function Revenue({ production, prices, totalRevenue }: RevenueProps) {
  const entries = (Object.keys(production) as Array<keyof ProductVolumes>)
    .filter(k => production[k] > 0)
    .map(k => ({ name: k, revenue: production[k] * prices[k] }))
    .sort((a, b) => b.revenue - a.revenue);

  return (
    <div className="revenue">
      <h3>Revenue: ${totalRevenue.toFixed(2)}/tick</h3>
      <div className="revenue-bars">
        {entries.map(({ name, revenue }) => (
          <div key={name} className="revenue-row">
            <span>{name}</span>
            <span>${revenue.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Wire all panels into App.tsx**

Update `src/ui/App.tsx` to import and render all panels. Add `previousPrices` state tracking:

```tsx
import { ProductionChart } from './ProductionChart';
import { PriceTicker } from './PriceTicker';
import { MassBalance } from './MassBalance';
import { Revenue } from './Revenue';
```

Add state for previous prices:
```tsx
const [prevPrices, setPrevPrices] = useState<ProductPrices | null>(null);
```

In the tick interval callback, before `setState(newState)`:
```tsx
setState(prev => {
  setPrevPrices(prev.prices);
  return newState;
});
```

Replace placeholder panels with:
```tsx
<div className="panel flow-panel">
  <FlowDiagram nodes={state.nodes} />
</div>
<div className="panel">
  <ProductionChart production={state.production} />
</div>
<div className="panel">
  <PriceTicker prices={state.prices} previousPrices={prevPrices} />
</div>
<div className="panel">
  <MassBalance
    input={{ fat: state.nodes.wholeMilk.fat, snf: state.nodes.wholeMilk.snf, water: state.nodes.wholeMilk.water }}
    error={state.massBalanceError}
  />
</div>
<div className="panel">
  <Revenue production={state.production} prices={state.prices} totalRevenue={state.revenue} />
</div>
```

- [ ] **Step 6: Add component styles to index.css**

```css
/* Production chart */
.production-chart h3, .price-ticker h3, .mass-balance h3, .revenue h3 {
  font-size: 14px; color: #7db8df; margin-bottom: 8px;
}

.bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 12px; }
.bar-label { width: 80px; text-align: right; color: #aaa; }
.bar-track { flex: 1; height: 16px; background: #1a1a2e; border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.1s; }
.bar-value { width: 60px; font-size: 11px; color: #888; }

/* Price ticker */
.price-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.price-item { display: flex; gap: 8px; font-size: 12px; align-items: center; }
.price-name { color: #aaa; width: 80px; }
.price-value { color: #e0e0e0; font-family: monospace; }

/* Mass balance */
.mass-balance table { width: 100%; font-size: 12px; border-collapse: collapse; }
.mass-balance th { text-align: left; color: #888; padding: 4px; border-bottom: 1px solid #333; }
.mass-balance td { padding: 4px; font-family: monospace; }

/* Revenue */
.revenue-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; }
.revenue-row span:first-child { color: #aaa; }
.revenue-row span:last-child { font-family: monospace; }
```

- [ ] **Step 7: Verify and commit**

```bash
git add src/ui/ProductionChart.tsx src/ui/PriceTicker.tsx src/ui/MassBalance.tsx src/ui/Revenue.tsx src/ui/App.tsx src/index.css
git commit -m "feat: add production, price, mass balance, and revenue dashboard panels"
```

---

### Task 11: Integration Test and Polish

**Goal:** Run the full system end-to-end, fix any issues, verify mass balance holds across different configs.

**Files:**
- Modify: any files needing fixes
- Create: `tests/engine/integration.test.ts`

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Integration test runs 100 ticks with config changes and mass balance stays < 0.1% error
- [ ] `npm run dev` shows working interactive dashboard
- [ ] Config changes visibly affect all downstream panels

**Verify:** `npx vitest run` → all tests PASS

**Steps:**

- [ ] **Step 1: Write integration test**

```typescript
// tests/engine/integration.test.ts
import { describe, it, expect } from 'vitest';
import { tick, DEFAULT_CONFIG } from '../src/engine/simulation';
import { CheeseType, PowderType, SimulationConfig } from '../src/engine/types';

describe('integration', () => {
  it('runs 100 ticks with default config and mass balance holds', () => {
    for (let i = 0; i < 100; i++) {
      const state = tick(DEFAULT_CONFIG, i);
      expect(Math.abs(state.massBalanceError.fat)).toBeLessThan(0.1);
      expect(Math.abs(state.massBalanceError.snf)).toBeLessThan(0.1);
      expect(Math.abs(state.massBalanceError.water)).toBeLessThan(1);
      expect(state.revenue).toBeGreaterThan(0);
    }
  });

  it('handles extreme configs without NaN or negative volumes', () => {
    const configs: Partial<SimulationConfig>[] = [
      { producer: { fatPercent: 3.0, snfPercent: 7.5, productionRate: 100 } },
      { producer: { fatPercent: 5.0, snfPercent: 9.5, productionRate: 5000 } },
      { separator: { targetCreamFatPercent: 30 } },
      { separator: { targetCreamFatPercent: 45 } },
      { skimSplitPercent: 0 },
      { skimSplitPercent: 100 },
      { creamSplitPercent: 0 },
      { creamSplitPercent: 100 },
      { cheesePlantA: { cheeseType: CheeseType.Parmesan }, cheesePlantB: { cheeseType: CheeseType.Parmesan } },
      { butterPlantA: { targetButterFatPercent: 78, powderType: PowderType.WMP } },
    ];

    for (const override of configs) {
      const config = { ...DEFAULT_CONFIG, ...override };
      const state = tick(config, 0);

      // No NaN
      expect(state.revenue).not.toBeNaN();
      expect(state.nodes.wholeMilk.volume).not.toBeNaN();

      // No negative volumes
      for (const val of Object.values(state.production)) {
        expect(val).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('changing cheese type shifts cream pool volume', () => {
    const configA = {
      ...DEFAULT_CONFIG,
      cheesePlantA: { cheeseType: CheeseType.Cheddar },
      cheesePlantB: { cheeseType: CheeseType.Cheddar },
    };
    const configB = {
      ...DEFAULT_CONFIG,
      cheesePlantA: { cheeseType: CheeseType.Parmesan },
      cheesePlantB: { cheeseType: CheeseType.Parmesan },
    };
    const stateA = tick(configA, 0);
    const stateB = tick(configB, 0);

    // Parmesan has higher casein:fat ratio → more excess cream
    expect(stateB.nodes.creamPool.fat).toBeGreaterThan(stateA.nodes.creamPool.fat);
  });
});
```

- [ ] **Step 2: Run all tests**

```bash
npx vitest run
```
Expected: all PASS

- [ ] **Step 3: Fix any failures, then commit**

```bash
git add tests/engine/integration.test.ts
git commit -m "feat: add integration tests verifying mass balance across configs"
```

- [ ] **Step 4: Final push**

```bash
git push
```
