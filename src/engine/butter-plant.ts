import { Stream, ButterPlantConfig, PowderType } from './types';

const BUTTER_SNF_FRACTION = 0.015;
const WMP_FAT_FRACTION = 0.26;
const FAT_RECOVERY = 0.99;

export function processButterPlant(
  cream: Stream,
  config: ButterPlantConfig,
): { butter: Stream; powder: Stream } {
  const butterFatFraction = config.targetButterFatPercent / 100;

  // Churn cream into butter and buttermilk
  const butterFat = cream.fat * FAT_RECOVERY;
  const butterVolume = butterFat / butterFatFraction;
  const butterSnf = butterVolume * BUTTER_SNF_FRACTION;
  const butterWater = butterVolume - butterFat - butterSnf;

  // Buttermilk is everything remaining (cream minus butter)
  const buttermilkFat = cream.fat - butterFat;
  const buttermilkSnf = cream.snf - butterSnf;
  const buttermilkWater = cream.water - butterWater;
  const buttermilkVolume = cream.volume - butterVolume;

  if (config.powderType === PowderType.WMP) {
    // WMP: add fat back from butter to reach target fat fraction in powder
    // Solve for X (fat transferred from butter to powder) such that:
    // (buttermilkFat + X) / (buttermilkVolume + X) = WMP_FAT_FRACTION
    const x = (WMP_FAT_FRACTION * buttermilkVolume - buttermilkFat) / (1 - WMP_FAT_FRACTION);

    const adjButterFat = butterFat - x;
    const adjButterVolume = butterVolume - x;
    const adjButter: Stream = {
      volume: adjButterVolume,
      fat: adjButterFat,
      snf: butterSnf,
      water: butterWater,
    };

    const powder: Stream = {
      volume: buttermilkVolume + x,
      fat: buttermilkFat + x,
      snf: buttermilkSnf,
      water: buttermilkWater,
    };

    return { butter: adjButter, powder };
  }

  // NFDM and BMP: spray-dry buttermilk as-is (powder volume = buttermilk volume,
  // water is retained in stream accounting for mass balance)
  const powder: Stream = {
    volume: buttermilkVolume,
    fat: buttermilkFat,
    snf: buttermilkSnf,
    water: buttermilkWater,
  };

  const butter: Stream = {
    volume: butterVolume,
    fat: butterFat,
    snf: butterSnf,
    water: butterWater,
  };

  return { butter, powder };
}
