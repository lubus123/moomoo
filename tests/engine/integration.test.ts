import { describe, it, expect } from 'vitest';
import { tick, DEFAULT_CONFIG } from '../../src/engine/simulation';
import { CheeseType, PowderType, SimulationConfig } from '../../src/engine/types';

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

      expect(state.revenue).not.toBeNaN();
      expect(state.nodes.wholeMilk.volume).not.toBeNaN();

      for (const val of Object.values(state.production)) {
        expect(val).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('changing cheese type changes cheese yield', () => {
    const configA = {
      ...DEFAULT_CONFIG,
      cheesePlantA: { cheeseType: CheeseType.Cheddar },
      cheesePlantB: { cheeseType: CheeseType.Cheddar },
    };
    const configB = {
      ...DEFAULT_CONFIG,
      cheesePlantA: { cheeseType: CheeseType.Mozzarella },
      cheesePlantB: { cheeseType: CheeseType.Mozzarella },
    };
    const stateA = tick(configA, 0);
    const stateB = tick(configB, 0);

    // Mozzarella has higher moisture → higher volume yield than cheddar
    expect(stateB.production.mozzarella).toBeGreaterThan(stateA.production.cheddar);
    // Different cheese types produce different whey volumes
    expect(stateA.production.whey).not.toBeCloseTo(stateB.production.whey, 0);
  });
});
