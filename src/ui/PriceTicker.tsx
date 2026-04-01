import { ProductPrices } from '@engine/types';

interface PriceTickerProps {
  prices: ProductPrices;
  previousPrices: ProductPrices | null;
}

export function PriceTicker({ prices, previousPrices }: PriceTickerProps) {
  const entries = Object.entries(prices) as Array<[keyof ProductPrices, number]>;

  return (
    <div className="price-ticker">
      <h3>Prices ($/lb)</h3>
      <div className="price-grid">
        {entries.map(([name, price]) => {
          const prev = previousPrices ? previousPrices[name] : price;
          const delta = price - prev;
          const arrow = delta > 0.001 ? '▲' : delta < -0.001 ? '▼' : '—';
          const color = delta > 0.001 ? '#4caf50' : delta < -0.001 ? '#f44336' : '#888';
          return (
            <div key={name} className="price-item">
              <span className="price-name">{name}</span>
              <span className="price-value">${price.toFixed(3)}</span>
              <span style={{ color }}>{arrow}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
