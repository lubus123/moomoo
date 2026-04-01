import { NodeOutputs, Stream } from '@engine/types';

interface FlowDiagramProps {
  nodes: NodeOutputs;
}

function fmt(n: number): string {
  return n < 10 ? n.toFixed(2) : n.toFixed(0);
}

function pct(part: number, total: number): string {
  if (total === 0) return '0%';
  return ((part / total) * 100).toFixed(1) + '%';
}

function StreamLabel({ stream, x, y }: { stream: Stream; x: number; y: number }) {
  return (
    <text x={x} y={y} fill="#aaa" fontSize="10" textAnchor="middle">
      <tspan x={x} dy="0">{fmt(stream.volume)} lbs</tspan>
      <tspan x={x} dy="12">F:{pct(stream.fat, stream.volume)} S:{pct(stream.snf, stream.volume)}</tspan>
    </text>
  );
}

function Node({ x, y, w, h, label, color }: { x: number; y: number; w: number; h: number; label: string; color: string }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={6} fill="none" stroke={color} strokeWidth={2} />
      <text x={x + w / 2} y={y + h / 2 + 4} fill={color} fontSize="12" textAnchor="middle" fontWeight="bold">{label}</text>
    </g>
  );
}

export function FlowDiagram({ nodes }: FlowDiagramProps) {
  return (
    <svg viewBox="0 0 700 520" style={{ width: '100%', height: '100%', minHeight: 400 }}>
      {/* Producer */}
      <Node x={275} y={10} w={150} h={36} label="Milk Producer" color="#7ddf7d" />
      <StreamLabel stream={nodes.wholeMilk} x={350} y={60} />
      <line x1={350} y1={46} x2={350} y2={85} stroke="#555" strokeWidth={1} />

      {/* Separator */}
      <Node x={275} y={85} w={150} h={36} label="Separator" color="#7db8df" />

      {/* Skim line (right) */}
      <line x1={425} y1={103} x2={530} y2={103} stroke="#555" />
      <line x1={530} y1={103} x2={530} y2={180} stroke="#555" />
      <StreamLabel stream={nodes.skim} x={530} y={140} />

      {/* Cream line (left) */}
      <line x1={275} y1={103} x2={170} y2={103} stroke="#555" />
      <line x1={170} y1={103} x2={170} y2={310} stroke="#555" />
      <StreamLabel stream={nodes.cream} x={170} y={140} />

      {/* Cheese Plants */}
      <Node x={440} y={180} w={120} h={36} label="Cheese A" color="#df7d7d" />
      <Node x={570} y={180} w={120} h={36} label="Cheese B" color="#df7d7d" />

      {/* Cheese outputs */}
      <StreamLabel stream={nodes.cheesePlantA.cheese} x={500} y={240} />
      <text x={500} y={262} fill="#df7d7d" fontSize="9" textAnchor="middle">cheese+whey</text>
      <StreamLabel stream={nodes.cheesePlantB.cheese} x={630} y={240} />
      <text x={630} y={262} fill="#df7d7d" fontSize="9" textAnchor="middle">cheese+whey</text>

      {/* Excess cream arrows */}
      <line x1={440} y1={216} x2={320} y2={310} stroke="#dfbf5f" strokeDasharray="4" />
      <line x1={570} y1={216} x2={320} y2={310} stroke="#dfbf5f" strokeDasharray="4" />
      <text x={370} y={275} fill="#dfbf5f" fontSize="9" textAnchor="middle">excess cream</text>

      {/* Cream Pool */}
      <Node x={110} y={310} w={150} h={36} label="Cream Pool" color="#dfbf5f" />
      <StreamLabel stream={nodes.creamPool} x={185} y={365} />

      {/* Butter Plants */}
      <line x1={145} y1={346} x2={100} y2={400} stroke="#555" />
      <line x1={225} y1={346} x2={270} y2={400} stroke="#555" />
      <Node x={30} y={400} w={130} h={36} label="Butter A" color="#dfbf5f" />
      <Node x={200} y={400} w={130} h={36} label="Butter B" color="#dfbf5f" />

      {/* Butter outputs */}
      <StreamLabel stream={nodes.butterPlantA.butter} x={95} y={460} />
      <text x={95} y={482} fill="#dfbf5f" fontSize="9" textAnchor="middle">butter+powder</text>
      <StreamLabel stream={nodes.butterPlantB.butter} x={265} y={460} />
      <text x={265} y={482} fill="#dfbf5f" fontSize="9" textAnchor="middle">butter+powder</text>
    </svg>
  );
}
