interface MassBalanceProps {
  input: { fat: number; snf: number; water: number };
  error: { fat: number; snf: number; water: number };
}

export function MassBalance({ input, error }: MassBalanceProps) {
  const rows = [
    { name: 'Fat', inVal: input.fat, err: error.fat },
    { name: 'SNF', inVal: input.snf, err: error.snf },
    { name: 'Water', inVal: input.water, err: error.water },
  ];

  return (
    <div className="mass-balance">
      <h3>Mass Balance Audit</h3>
      <table>
        <thead>
          <tr><th>Component</th><th>In (lbs)</th><th>Error (lbs)</th><th>Error %</th></tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const errPct = r.inVal > 0 ? (Math.abs(r.err) / r.inVal) * 100 : 0;
            const isOk = errPct < 0.1;
            return (
              <tr key={r.name}>
                <td>{r.name}</td>
                <td>{r.inVal.toFixed(2)}</td>
                <td style={{ color: isOk ? '#4caf50' : '#f44336' }}>{r.err.toFixed(4)}</td>
                <td style={{ color: isOk ? '#4caf50' : '#f44336' }}>{errPct.toFixed(3)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
