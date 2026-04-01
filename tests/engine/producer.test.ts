import { describe, it, expect } from 'vitest';
import { produce } from '../../src/engine/producer';
import { validateStream } from '../../src/engine/types';

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
