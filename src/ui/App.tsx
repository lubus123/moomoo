import { useState, useRef, useEffect } from 'react';
import { SimulationConfig, SimulationState, ProductPrices } from '@engine/types';
import { tick, DEFAULT_CONFIG } from '@engine/simulation';
import { Controls } from './Controls';
import { FlowDiagram } from './FlowDiagram';
import { ProductionChart } from './ProductionChart';
import { PriceTicker } from './PriceTicker';
import { MassBalance } from './MassBalance';
import { Revenue } from './Revenue';

export function App() {
  const [config, setConfig] = useState<SimulationConfig>(DEFAULT_CONFIG);
  const [state, setState] = useState<SimulationState>(() => tick(DEFAULT_CONFIG, 0));
  const [prevPrices, setPrevPrices] = useState<ProductPrices | null>(null);
  const [running, setRunning] = useState(false);
  const [ticksPerSecond, setTicksPerSecond] = useState(10);
  const tickRef = useRef(0);
  const configRef = useRef(config);
  configRef.current = config;

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => {
      tickRef.current += 1;
      const newState = tick(configRef.current, tickRef.current);
      setState(prev => {
        setPrevPrices(prev.prices);
        return newState;
      });
    }, 1000 / ticksPerSecond);
    return () => clearInterval(interval);
  }, [running, ticksPerSecond]);

  return (
    <div className="app">
      <Controls
        config={config}
        onChange={setConfig}
        running={running}
        onToggleRun={() => setRunning(r => !r)}
        ticksPerSecond={ticksPerSecond}
        onTicksPerSecondChange={setTicksPerSecond}
      />
      <div className="dashboard">
        <h2>Moomoo Dashboard</h2>
        <div className="tick-counter">Tick: {state.tick}</div>
        <div className="placeholder-panels">
          <div className="panel flow-panel">
            <FlowDiagram nodes={state.nodes} />
          </div>
          <div className="panel">
            <ProductionChart production={state.production} />
          </div>
          <div className="panel">
            <PriceTicker prices={state.prices} previousPrices={prevPrices} />
          </div>
          <div className="panel">
            <MassBalance
              input={{ fat: state.nodes.wholeMilk.fat, snf: state.nodes.wholeMilk.snf, water: state.nodes.wholeMilk.water }}
              error={state.massBalanceError}
            />
          </div>
          <div className="panel">
            <Revenue production={state.production} prices={state.prices} totalRevenue={state.revenue} />
          </div>
        </div>
      </div>
    </div>
  );
}
