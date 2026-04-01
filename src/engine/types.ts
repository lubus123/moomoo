export interface Stream {
  volume: number;
  fat: number;
  snf: number;
  water: number;
}

export function createStream(volume: number, fatFraction: number, snfFraction: number): Stream {
  const fat = volume * fatFraction;
  const snf = volume * snfFraction;
  const water = volume - fat - snf;
  return { volume, fat, snf, water };
}

export function validateStream(s: Stream): boolean {
  return Math.abs(s.fat + s.snf + s.water - s.volume) < 0.001;
}

export const EMPTY_STREAM: Stream = { volume: 0, fat: 0, snf: 0, water: 0 };

export function addStreams(...streams: Stream[]): Stream {
  const result = { volume: 0, fat: 0, snf: 0, water: 0 };
  for (const s of streams) {
    result.volume += s.volume;
    result.fat += s.fat;
    result.snf += s.snf;
    result.water += s.water;
  }
  return result;
}

export enum CheeseType {
  Cheddar = 'cheddar',
  Mozzarella = 'mozzarella',
  Swiss = 'swiss',
  Parmesan = 'parmesan',
}

export enum PowderType {
  NFDM = 'nfdm',
  BMP = 'bmp',
  WMP = 'wmp',
}

export interface ProducerConfig {
  fatPercent: number;
  snfPercent: number;
  productionRate: number;
}

export interface SeparatorConfig {
  targetCreamFatPercent: number;
}

export interface ButterPlantConfig {
  targetButterFatPercent: number;
  powderType: PowderType;
}

export interface CheesePlantConfig {
  cheeseType: CheeseType;
}

export interface SimulationConfig {
  producer: ProducerConfig;
  separator: SeparatorConfig;
  skimSplitPercent: number;
  creamSplitPercent: number;
  butterPlantA: ButterPlantConfig;
  butterPlantB: ButterPlantConfig;
  cheesePlantA: CheesePlantConfig;
  cheesePlantB: CheesePlantConfig;
}

export interface ProductPrices {
  butter: number;
  nfdm: number;
  bmp: number;
  wmp: number;
  cheddar: number;
  mozzarella: number;
  swiss: number;
  parmesan: number;
  whey: number;
}

export interface ProductVolumes {
  butter: number;
  nfdm: number;
  bmp: number;
  wmp: number;
  cheddar: number;
  mozzarella: number;
  swiss: number;
  parmesan: number;
  whey: number;
}

export interface NodeOutputs {
  wholeMilk: Stream;
  cream: Stream;
  skim: Stream;
  cheesePlantA: { cheese: Stream; whey: Stream; excessCream: Stream };
  cheesePlantB: { cheese: Stream; whey: Stream; excessCream: Stream };
  creamPool: Stream;
  butterPlantA: { butter: Stream; powder: Stream };
  butterPlantB: { butter: Stream; powder: Stream };
}

export interface SimulationState {
  tick: number;
  config: SimulationConfig;
  nodes: NodeOutputs;
  production: ProductVolumes;
  prices: ProductPrices;
  revenue: number;
  massBalanceError: { fat: number; snf: number; water: number };
}
