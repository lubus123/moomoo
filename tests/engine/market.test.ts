import { describe, it, expect } from 'vitest';
import { calculatePrices, calculateRevenue, DEFAULT_MARKET } from '../../src/engine/market';

describe('market', () => {
  it('returns base price when supply equals demand', () => {
    const supply = { butter: 100, nfdm: 50, bmp: 0, wmp: 0, cheddar: 80, mozzarella: 0, swiss: 0, parmesan: 0, whey: 200 };
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
