import { describe, it, expect } from 'vitest';
import { tick, DEFAULT_CONFIG } from '../../src/engine/simulation';
import { CheeseType, PowderType } from '../../src/engine/types';

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
