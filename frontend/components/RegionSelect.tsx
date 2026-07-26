"use client";

function formatRegionLabel(region: string): string {
  return region
    .split("-")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export default function RegionSelect({
  regions,
  value,
  onChange,
}: {
  regions: string[];
  value: string;
  onChange: (region: string) => void;
}) {
  return (
    <select className="select" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Grid region">
      {regions.map((region) => (
        <option key={region} value={region}>
          {formatRegionLabel(region)}
        </option>
      ))}
    </select>
  );
}
