import { Stream, SeparatorConfig } from './types';

const SKIM_FAT_FRACTION = 0.001;

export function separate(
  milk: Stream,
  config: SeparatorConfig,
): { cream: Stream; skim: Stream } {
  const f_m = milk.fat / milk.volume;
  const f_c = config.targetCreamFatPercent / 100;
  const f_s = SKIM_FAT_FRACTION;

  const creamVolume = milk.volume * (f_m - f_s) / (f_c - f_s);
  const skimVolume = milk.volume - creamVolume;

  const creamFat = creamVolume * f_c;
  const skimFat = milk.fat - creamFat;

  const creamFraction = creamVolume / milk.volume;
  const creamSnf = milk.snf * creamFraction;
  const skimSnf = milk.snf - creamSnf;
  const creamWater = creamVolume - creamFat - creamSnf;
  const skimWater = skimVolume - skimFat - skimSnf;

  return {
    cream: { volume: creamVolume, fat: creamFat, snf: creamSnf, water: creamWater },
    skim: { volume: skimVolume, fat: skimFat, snf: skimSnf, water: skimWater },
  };
}
