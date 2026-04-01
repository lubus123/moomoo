import { ProductVolumes, ProductPrices } from './types';

export interface MarketParams {
  basePrice: number;
  demand: number;
  elasticity: number;
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
