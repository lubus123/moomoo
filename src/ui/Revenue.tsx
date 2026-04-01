import { ProductVolumes, ProductPrices } from '@engine/types';

interface RevenueProps {
  production: ProductVolumes;
  prices: ProductPrices;
  totalRevenue: number;
}

export function Revenue({ production, prices, totalRevenue }: RevenueProps) {
  const entries = (Object.keys(production) as Array<keyof ProductVolumes>)
    .filter(k => production[k] > 0)
    .map(k => ({ name: k, revenue: production[k] * prices[k] }))
    .sort((a, b) => b.revenue - a.revenue);

  return (
    <div className="revenue">
      <h3>Revenue: ${totalRevenue.toFixed(2)}/tick</h3>
      <div className="revenue-bars">
        {entries.map(({ name, revenue }) => (
          <div key={name} className="revenue-row">
            <span>{name}</span>
            <span>${revenue.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
