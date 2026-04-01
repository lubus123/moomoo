import { Stream, ProducerConfig, createStream } from './types';

export function produce(config: ProducerConfig): Stream {
  return createStream(
    config.productionRate,
    config.fatPercent / 100,
    config.snfPercent / 100,
  );
}
