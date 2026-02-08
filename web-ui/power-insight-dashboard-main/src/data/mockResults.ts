import type { ResultsData } from "@/types/results";

export const mockResults: ResultsData = {
  generated_utc: "2025-01-15T14:32:00Z",
  executive_summary: {
    recommended_option: "Option B - Active Filter + 12-Pulse",
    thdv_limit: 5.0,
    thdv_pass: true,
    tdd_limit: 8.0,
    tdd_pass: true,
    risk_voltage: "LOW",
    risk_current: "MEDIUM",
    isc_il_ratio: 42.5,
    worst_harmonic: 5,
    key_takeaways: [
      "System meets IEEE-519 limits under all tested scenarios",
      "5th harmonic dominates the spectrum at 4.2% THDv",
      "Active filtering recommended for future load growth beyond 150%",
      "Current Isc/IL ratio of 42.5 places system in <50 category",
      "Minimum SSC of 85 MVA required to maintain compliance at full load"
    ]
  },
  inputs_assumptions: {
    "Facility Load": "12 MW",
    "Power Factor": "0.92 lagging",
    "UPS Topology": "Double Conversion",
    "UPS Rating": "2000 kVA",
    "Number of UPS Units": "6",
    "Utility Voltage": "13.8 kV",
    "Transformer Impedance": "5.75%",
    "Available Fault Current": "500 MVA",
    "Load Diversity Factor": "0.85",
    "IT Load Profile": "Mixed (servers + storage)",
    "Harmonic Spectrum": "Typical 6-pulse rectifier"
  },
  tables: {
    top_scenarios_ranked: {
      columns: ["Rank", "Scenario", "THDv (%)", "TDD (%)", "Status", "Risk Score"],
      rows: [
        [1, "Baseline - No Mitigation", 8.4, 12.1, "FAIL", 85],
        [2, "12-Pulse Rectifier Only", 5.2, 9.3, "FAIL", 62],
        [3, "Passive Filter (5th + 7th)", 4.1, 7.2, "PASS", 35],
        [4, "Active Filter + 12-Pulse", 2.8, 4.5, "PASS", 15],
        [5, "18-Pulse + Passive Filter", 3.2, 5.8, "PASS", 22]
      ]
    },
    tipping_points_min_ssc_required: {
      columns: ["Load Level (%)", "Min SSC (MVA)", "THDv at Min SSC", "Margin (%)"],
      rows: [
        [75, 65, 4.8, 4.2],
        [100, 85, 4.9, 2.0],
        [125, 110, 5.0, 0.0],
        [150, 145, 5.2, -4.0],
        [175, 190, 5.8, -16.0]
      ]
    }
  },
  series: {
    thdv_vs_sc_mva: {
      points: [
        { x: 50, y: 7.2 },
        { x: 75, y: 5.8 },
        { x: 100, y: 5.0 },
        { x: 125, y: 4.4 },
        { x: 150, y: 4.0 },
        { x: 200, y: 3.5 },
        { x: 250, y: 3.1 },
        { x: 300, y: 2.8 }
      ]
    }
  },
  artifacts: {
    report_html: "<html><body><h1>Full Analysis Report</h1><p>Detailed findings...</p></body></html>",
    plots: []
  },
  disclaimer: "This analysis is for preliminary screening purposes only. Results should be validated with detailed power system studies and field measurements. IEEE-519 compliance depends on actual site conditions, utility characteristics, and load behavior that may differ from modeled assumptions."
};
