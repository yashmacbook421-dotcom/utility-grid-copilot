export default function StatTile({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div>
      <p className="stat-tile-label">{label}</p>
      <p className="stat-tile-value">
        {value}
        {unit ? <span className="unit">{unit}</span> : null}
      </p>
    </div>
  );
}
