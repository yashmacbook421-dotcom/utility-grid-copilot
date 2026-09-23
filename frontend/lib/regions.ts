export const REGION_PROFILES: Record<string, { has_temperature: boolean }> = {
  california: { has_temperature: true },
  smud: { has_temperature: true },
  georgia: { has_temperature: true },
};

export const REGION_COORDS: Record<string, [number, number]> = {
  california: [36.75, -119.77],
  smud: [38.58, -121.49],
  georgia: [33.75, -84.39],
};

export const EIA_RESPONDENTS: Record<string, string> = {
  california: "CISO",
  smud: "BANC",
  georgia: "SOCO",
};
