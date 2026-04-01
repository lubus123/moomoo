import { describe, it, expect } from 'vitest';
import { processCheese, CHEESE_PARAMS } from '../../src/engine/cheese-plant';
import { createStream, validateStream, CheeseType } from '../../src/engine/types';

describe('cheese plant', () => {
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
