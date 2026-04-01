import { ProductVolumes } from '@engine/types';

interface ProductionChartProps {
  production: ProductVolumes;
}

const COLORS: Record<string, string> = {
  butter: '#dfbf5f', nfdm: '#8ab4f8', bmp: '#a8d8ea', wmp: '#f8d8a8',
  cheddar: '#df7d7d', mozzarella: '#e8a87c', swiss: '#d4a574', parmesan: '#c49a6c',
  whey: '#88c999',
};

export function ProductionChart({ production }: ProductionChartProps) {
  const entries = Object.entries(production).filter(([, v]) => v > 0);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="production-chart">
      <h3>Production (lbs/tick)</h3>
      {entries.map(([name, vol]) => (
        <div key={name} className="bar-row">
          <span className="bar-label">{name}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(vol / max) * 100}%`, background: COLORS[name] || '#888' }} />
          </div>
          <span className="bar-value">{vol.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}
