export interface ExecutiveSummary {
  recommended_option: string;
  thdv_limit: number;
  thdv_pass: boolean;
  tdd_limit: number;
  tdd_pass: boolean;
  risk_voltage: "LOW" | "MEDIUM" | "HIGH";
  risk_current: "LOW" | "MEDIUM" | "HIGH";
  isc_il_ratio: number;
  worst_harmonic: number;
  key_takeaways: string[];
}

export interface TableData {
  columns: string[];
  rows: (string | number)[][];
}

export interface SeriesPoint {
  x: number;
  y: number;
}

export interface Artifacts {
  report_html?: string;
  plots?: string[];
}

export interface ResultsData {
  generated_utc: string;
  executive_summary: ExecutiveSummary;
  inputs_assumptions: Record<string, string | number>;
  tables: {
    top_scenarios_ranked: TableData;
    tipping_points_min_ssc_required: TableData;
  };
  series?: {
    thdv_vs_sc_mva?: {
      points: SeriesPoint[];
    };
  };
  artifacts?: Artifacts;
  disclaimer: string;
}
