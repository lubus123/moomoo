import { SimulationConfig, CheeseType, PowderType } from '@engine/types';

interface ControlsProps {
  config: SimulationConfig;
  onChange: (config: SimulationConfig) => void;
  running: boolean;
  onToggleRun: () => void;
  ticksPerSecond: number;
  onTicksPerSecondChange: (tps: number) => void;
}

export function Controls({ config, onChange, running, onToggleRun, ticksPerSecond, onTicksPerSecondChange }: ControlsProps) {
  const update = (path: string, value: number | string) => {
    const next = structuredClone(config);
    const parts = path.split('.');
    let obj: any = next;
    for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
    obj[parts[parts.length - 1]] = value;
    onChange(next);
  };

  return (
    <div className="controls">
      <h2>Controls</h2>
      <button className="play-btn" onClick={onToggleRun}>
        {running ? '⏸ Pause' : '▶ Play'}
      </button>
      <label>
        Speed: {ticksPerSecond} ticks/sec
        <input type="range" min={1} max={60} value={ticksPerSecond}
          onChange={e => onTicksPerSecondChange(Number(e.target.value))} />
      </label>

      <fieldset>
        <legend>Milk Producer</legend>
        <label>Fat %: {config.producer.fatPercent.toFixed(1)}
          <input type="range" min={3.0} max={5.0} step={0.1} value={config.producer.fatPercent}
            onChange={e => update('producer.fatPercent', Number(e.target.value))} /></label>
        <label>SNF %: {config.producer.snfPercent.toFixed(1)}
          <input type="range" min={7.5} max={9.5} step={0.1} value={config.producer.snfPercent}
            onChange={e => update('producer.snfPercent', Number(e.target.value))} /></label>
        <label>Production: {config.producer.productionRate} lbs/tick
          <input type="range" min={100} max={5000} step={100} value={config.producer.productionRate}
            onChange={e => update('producer.productionRate', Number(e.target.value))} /></label>
      </fieldset>

      <fieldset>
        <legend>Separator</legend>
        <label>Cream Fat %: {config.separator.targetCreamFatPercent}
          <input type="range" min={30} max={45} step={1} value={config.separator.targetCreamFatPercent}
            onChange={e => update('separator.targetCreamFatPercent', Number(e.target.value))} /></label>
      </fieldset>

      <fieldset>
        <legend>Routing</legend>
        <label>Skim → Cheese A: {config.skimSplitPercent}%
          <input type="range" min={0} max={100} step={5} value={config.skimSplitPercent}
            onChange={e => update('skimSplitPercent', Number(e.target.value))} /></label>
        <label>Cream → Butter A: {config.creamSplitPercent}%
          <input type="range" min={0} max={100} step={5} value={config.creamSplitPercent}
            onChange={e => update('creamSplitPercent', Number(e.target.value))} /></label>
      </fieldset>

      <fieldset>
        <legend>Butter Plant A</legend>
        <label>Butter Fat %: {config.butterPlantA.targetButterFatPercent}
          <input type="range" min={78} max={84} step={1} value={config.butterPlantA.targetButterFatPercent}
            onChange={e => update('butterPlantA.targetButterFatPercent', Number(e.target.value))} /></label>
        <label>Powder Type:
          <select value={config.butterPlantA.powderType}
            onChange={e => update('butterPlantA.powderType', e.target.value)}>
            {Object.values(PowderType).map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select></label>
      </fieldset>

      <fieldset>
        <legend>Butter Plant B</legend>
        <label>Butter Fat %: {config.butterPlantB.targetButterFatPercent}
          <input type="range" min={78} max={84} step={1} value={config.butterPlantB.targetButterFatPercent}
            onChange={e => update('butterPlantB.targetButterFatPercent', Number(e.target.value))} /></label>
        <label>Powder Type:
          <select value={config.butterPlantB.powderType}
            onChange={e => update('butterPlantB.powderType', e.target.value)}>
            {Object.values(PowderType).map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select></label>
      </fieldset>

      <fieldset>
        <legend>Cheese Plant A</legend>
        <label>Cheese Type:
          <select value={config.cheesePlantA.cheeseType}
            onChange={e => update('cheesePlantA.cheeseType', e.target.value)}>
            {Object.values(CheeseType).map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select></label>
      </fieldset>

      <fieldset>
        <legend>Cheese Plant B</legend>
        <label>Cheese Type:
          <select value={config.cheesePlantB.cheeseType}
            onChange={e => update('cheesePlantB.cheeseType', e.target.value)}>
            {Object.values(CheeseType).map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
          </select></label>
      </fieldset>
    </div>
  );
}
