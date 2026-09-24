// Static navigation shell for drilling into a state's grid regions. Only
// leaf nodes with a `regionId` are real, forecastable regions backed by the
// API (see app/data/regions.py on the backend) — everything else is a
// display-only waypoint until it gets its own data source.

export interface HierarchyNode {
  id: string;
  label: string;
  sublabel?: string;
  /** Backend region id — set only on nodes the API can actually forecast. */
  regionId?: string;
  children?: HierarchyNode[];
}

export const CALIFORNIA: HierarchyNode = {
  id: "california",
  label: "California",
  sublabel: "Statewide (CAISO)",
  regionId: "california",
  children: [
    {
      id: "sacramento",
      label: "Sacramento",
      sublabel: "County",
      children: [
        {
          id: "smud",
          label: "SMUD",
          sublabel: "Sacramento Municipal Utility District",
          regionId: "smud",
        },
        {
          id: "pge-sacramento",
          label: "PG&E",
          sublabel: "Pacific Gas & Electric — Sacramento service area",
        },
      ],
    },
    { id: "bay-area", label: "Bay Area", sublabel: "PG&E" },
    { id: "los-angeles", label: "Los Angeles", sublabel: "LADWP / SCE" },
    { id: "san-diego", label: "San Diego", sublabel: "SDG&E" },
  ],
};

export const GEORGIA: HierarchyNode = {
  id: "georgia",
  label: "Georgia",
  sublabel: "Statewide (Southern Company / SOCO)",
  regionId: "georgia",
  children: [
    { id: "atlanta", label: "Atlanta", sublabel: "Georgia Power" },
    { id: "savannah", label: "Savannah", sublabel: "Georgia Power" },
    { id: "augusta", label: "Augusta", sublabel: "Georgia Power" },
  ],
};

export const STATES: HierarchyNode[] = [CALIFORNIA, GEORGIA];
