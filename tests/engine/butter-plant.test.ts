import { describe, it, expect } from 'vitest';
import { processButterPlant } from '../../src/engine/butter-plant';
import { validateStream, PowderType } from '../../src/engine/types';

describe('butter plant', () => {
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
