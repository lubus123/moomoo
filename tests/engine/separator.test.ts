import { describe, it, expect } from 'vitest';
import { separate } from '../../src/engine/separator';
import { createStream, validateStream } from '../../src/engine/types';

describe('separator', () => {
  const wholeMilk = createStream(1000, 0.04, 0.09);

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
