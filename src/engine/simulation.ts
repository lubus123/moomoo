import {
  SimulationConfig, SimulationState, ProductVolumes, Stream,
  CheeseType, PowderType, addStreams, EMPTY_STREAM,
} from './types';
import { produce } from './producer';
import { separate } from './separator';
import { processCheese } from './cheese-plant';
import { processButterPlant } from './butter-plant';
import { calculatePrices, calculateRevenue, DEFAULT_MARKET } from './market';

export const DEFAULT_CONFIG: SimulationConfig = {
  producer: { fatPercent: 4.0, snfPercent: 9.0, productionRate: 1000 },
  separator: { targetCreamFatPercent: 40 },
  skimSplitPercent: 50,
  creamSplitPercent: 50,
  butterPlantA: { targetButterFatPercent: 82, powderType: PowderType.NFDM },
  butterPlantB: { targetButterFatPercent: 80, powderType: PowderType.BMP },
  cheesePlantA: { cheeseType: CheeseType.Cheddar },
  cheesePlantB: { cheeseType: CheeseType.Mozzarella },
};

function splitStream(stream: Stream, fractionA: number): [Stream, Stream] {
  const fractionB = 1 - fractionA;
  return [
    {
      volume: stream.volume * fractionA,
      fat: stream.fat * fractionA,
      snf: stream.snf * fractionA,
      water: stream.water * fractionA,
    },
    {
      volume: stream.volume * fractionB,
      fat: stream.fat * fractionB,
      snf: stream.snf * fractionB,
      water: stream.water * fractionB,
    },
  ];
}

export function tick(config: SimulationConfig, tickNum: number): SimulationState {
  // 1. Produce whole milk
  const wholeMilk = produce(config.producer);

  // 2. Separate into cream and skim
  const { cream: separatorCream, skim } = separate(wholeMilk, config.separator);

  // 3. Split skim between cheese plants A and B
  const [skimA, skimB] = splitStream(skim, config.skimSplitPercent / 100);

  // 4. Process each cheese plant
  const cheeseA = processCheese(skimA, config.cheesePlantA);
  const cheeseB = processCheese(skimB, config.cheesePlantB);

  // 5. Cream pool: separator cream + excess cream from both cheese plants
  const creamPool = addStreams(separatorCream, cheeseA.excessCream, cheeseB.excessCream);

  // 6. Split cream pool between butter plants A and B
  const [creamForA, creamForB] = splitStream(creamPool, config.creamSplitPercent / 100);

  // 7. Process each butter plant
  const butterA = processButterPlant(creamForA, config.butterPlantA);
  const butterB = processButterPlant(creamForB, config.butterPlantB);

  // 8. Aggregate production volumes by product name
  const production: ProductVolumes = {
    butter: butterA.butter.volume + butterB.butter.volume,
    nfdm: 0,
    bmp: 0,
    wmp: 0,
    cheddar: 0,
    mozzarella: 0,
    swiss: 0,
    parmesan: 0,
    whey: cheeseA.whey.volume + cheeseB.whey.volume,
  };

  production[config.cheesePlantA.cheeseType] += cheeseA.cheese.volume;
  production[config.cheesePlantB.cheeseType] += cheeseB.cheese.volume;
  production[config.butterPlantA.powderType] += butterA.powder.volume;
  production[config.butterPlantB.powderType] += butterB.powder.volume;

  // 9. Market pricing and revenue
  const prices = calculatePrices(production, DEFAULT_MARKET);
  const revenue = calculateRevenue(production, prices);

  // 10. Mass balance audit: whole milk in vs. all product streams out
  const totalOut = addStreams(
    cheeseA.cheese, cheeseB.cheese,
    cheeseA.whey, cheeseB.whey,
    butterA.butter, butterB.butter,
    butterA.powder, butterB.powder,
  );
  const massBalanceError = {
    fat: wholeMilk.fat - totalOut.fat,
    snf: wholeMilk.snf - totalOut.snf,
    water: wholeMilk.water - totalOut.water,
  };

  return {
    tick: tickNum,
    config,
    nodes: {
      wholeMilk,
      cream: separatorCream,
      skim,
      cheesePlantA: cheeseA,
      cheesePlantB: cheeseB,
      creamPool,
      butterPlantA: butterA,
      butterPlantB: butterB,
    },
    production,
    prices,
    revenue,
    massBalanceError,
  };
}
