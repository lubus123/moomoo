import { Stream, CheesePlantConfig, CheeseType, EMPTY_STREAM } from './types';

export interface CheeseParams {
  moisture: number;
  fatRecovery: number;
  caseinFatRatio: number;
  caseinRecovery: number;
}

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

  const casein = milk.snf * CASEIN_FRACTION_OF_SNF;
  const targetFat = casein / params.caseinFatRatio;
  const availableFat = milk.fat;
  const fatForCheese = Math.min(targetFat, availableFat);
  const excessFat = availableFat - fatForCheese;

  const excessCream: Stream = excessFat > 0.001
    ? { volume: excessFat, fat: excessFat, snf: 0, water: 0 }
    : { ...EMPTY_STREAM };

  const stdMilkFat = fatForCheese;

  const recoveredFat = stdMilkFat * params.fatRecovery;
  const recoveredCasein = casein * params.caseinRecovery;
  const cheeseSolids = recoveredFat + recoveredCasein;
  const cheeseVolume = cheeseSolids / (1 - params.moisture);
  const cheeseWater = cheeseVolume - cheeseSolids;
  const cheeseFat = recoveredFat;
  const cheeseSnf = recoveredCasein;

  const wheyFat = stdMilkFat - cheeseFat;
  const wheySnf = milk.snf - cheeseSnf;
  const wheyWater = milk.water - cheeseWater;
  const wheyVolume = wheyFat + wheySnf + wheyWater;

  return {
    cheese: { volume: cheeseVolume, fat: cheeseFat, snf: cheeseSnf, water: cheeseWater },
    whey: { volume: wheyVolume, fat: wheyFat, snf: wheySnf, water: wheyWater },
    excessCream: excessCream,
  };
}
