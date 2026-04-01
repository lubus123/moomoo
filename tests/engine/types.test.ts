import { describe, it, expect } from 'vitest';
import { createStream, validateStream, CheeseType, PowderType } from '../../src/engine/types';

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
