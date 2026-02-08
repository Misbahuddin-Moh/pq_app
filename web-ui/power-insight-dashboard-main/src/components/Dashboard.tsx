import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Activity,
  Zap,
  AlertTriangle,
  Target,
  Download,
  FileText,
  Lightbulb,
  CheckCircle2,
  Settings2,
  Play,
  Link as LinkIcon,
  PanelLeft,
  PanelLeftClose,
  X,
} from "lucide-react";
import { LoadResultsPanel } from "./LoadResultsPanel";
import { SummaryCard } from "./SummaryCard";
import { DataTable } from "./DataTable";
import { KeyValueTable } from "./KeyValueTable";
import { ThdvChart } from "./ThdvChart";
import { mockResults } from "@/data/mockResults";
import type { ResultsData } from "@/types/results";

type TabKey = "results" | "run-analysis";
type TopologyMode =
  | "all"
  | "6pulse_typical"
  | "12pulse_typical"
  | "18pulse_typical"
  | "afe_low_harm";

type Preset = {
  key: string;
  label: string;
  description?: string;
  values: {
    vllV: number;
    freqHz: number;
    demandKw: number;
    loadPu: number;
    pfDisp: number;
    eff: number;
    kwIsOutput: boolean;
    scMva: number;
    zExp: number;
    thdvLimit: number;
    topologyMode: TopologyMode;
    enableSweeps: boolean;
  };
};

const PRESETS: Preset[] = [
  {
    key: "typical_415v_colo",
    label: "Typical 415 V colo (baseline)",
    description: "Sample-like defaults; broad topology sweep.",
    values: {
      vllV: 415.0,
      freqHz: 60.0,
      demandKw: 1000.0,
      loadPu: 0.6,
      pfDisp: 0.99,
      eff: 0.96,
      kwIsOutput: true,
      scMva: 50.0,
      zExp: 1.0,
      thdvLimit: 5.0,
      topologyMode: "all",
      enableSweeps: true,
    },
  },
  {
    key: "weak_pcc",
    label: "Weak PCC (low SC MVA)",
    description: "Stresses THDv; useful for risk screening.",
    values: {
      vllV: 415.0,
      freqHz: 60.0,
      demandKw: 1500.0,
      loadPu: 0.8,
      pfDisp: 0.98,
      eff: 0.96,
      kwIsOutput: true,
      scMva: 20.0,
      zExp: 1.0,
      thdvLimit: 5.0,
      topologyMode: "all",
      enableSweeps: true,
    },
  },
  {
    key: "stiff_pcc",
    label: "Stiff PCC (high SC MVA)",
    description: "Strong utility; often low THDv margin risk.",
    values: {
      vllV: 415.0,
      freqHz: 60.0,
      demandKw: 2000.0,
      loadPu: 0.8,
      pfDisp: 0.99,
      eff: 0.97,
      kwIsOutput: true,
      scMva: 250.0,
      zExp: 1.0,
      thdvLimit: 5.0,
      topologyMode: "all",
      enableSweeps: true,
    },
  },
  {
    key: "afe_only",
    label: "AFE-only screening",
    description: "Modern AFE UPS focus; no legacy topology comparisons.",
    values: {
      vllV: 415.0,
      freqHz: 60.0,
      demandKw: 1500.0,
      loadPu: 0.7,
      pfDisp: 0.99,
      eff: 0.97,
      kwIsOutput: true,
      scMva: 50.0,
      zExp: 1.0,
      thdvLimit: 5.0,
      topologyMode: "afe_low_harm",
      enableSweeps: true,
    },
  },
];

const BACKEND_BASE_URL = "https://pq-app-backend.onrender.com";

type ResultsWithArtifacts = ResultsData & {
  schema_version?: string;
  api_artifacts?: {
    results_url?: string;
    report_html_url?: string;
    plots?: { name: string; url: string }[];
    raw?: { name: string; url: string }[];
    [k: string]: any;
  };
  executive_summary?: any;
  series?: any;
};

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3 min-h-[20px]">
        <label className="text-sm font-medium text-foreground">{label}</label>
        {hint ? (
          <span className="text-xs text-muted-foreground hidden md:inline">
            {hint}
          </span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={[
        "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground",
        "placeholder:text-muted-foreground",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
        props.className ?? "",
      ].join(" ")}
    />
  );
}

function SelectInput(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={[
        "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
        props.className ?? "",
      ].join(" ")}
    />
  );
}

function yamlNumber(n: number) {
  if (!Number.isFinite(n)) return "0.0";
  const s = n.toString();
  return s.includes("e") || s.includes("E") ? n.toFixed(6) : s;
}

function getApiUrl(relOrAbs?: string) {
  if (!relOrAbs) return undefined;
  if (relOrAbs.startsWith("http://") || relOrAbs.startsWith("https://"))
    return relOrAbs;
  return `${BACKEND_BASE_URL}${relOrAbs}`;
}

function toChartPoints(points: any): { x: number; y: number }[] {
  if (!points) return [];
  if (Array.isArray(points) && points.length > 0 && Array.isArray(points[0])) {
    return (points as any[]).map((p) => ({ x: Number(p[0]), y: Number(p[1]) }));
  }
  if (Array.isArray(points) && points.length > 0 && typeof points[0] === "object") {
    return (points as any[]).map((p) => ({ x: Number(p.x), y: Number(p.y) }));
  }
  return [];
}

function tippingOptionsFor(topologyMode: TopologyMode): string[] {
  const AFE = "AFE (low low-order harmonics) (no filter)";
  const P18 = "18-pulse (typical) (no filter)";
  const P12 = "12-pulse (typical) (no filter)";
  const P6 = "6-pulse (typical) (no filter)";

  const P18_AF = "18-pulse (typical) + active_filter_like";
  const P12_AF = "12-pulse (typical) + active_filter_like";
  const P6_AF = "6-pulse (typical) + active_filter_like";

  switch (topologyMode) {
    case "afe_low_harm":
      return [AFE];
    case "18pulse_typical":
      return [P18, P18_AF];
    case "12pulse_typical":
      return [P12, P12_AF];
    case "6pulse_typical":
      return [P6, P6_AF];
    case "all":
    default:
      return [AFE, P18, P12, P6, P18_AF, P12_AF, P6_AF];
  }
}

function buildConfigYaml(params: {
  vll_v: number;
  frequency_hz: number;
  demand_kw: number;
  load_pu: number;
  pf_displacement: number;
  efficiency: number;
  kw_is_output: boolean;
  sc_mva: number;
  z_exp: number;
  thdv_limit_pct: number;
  topology_mode: TopologyMode;
  enable_sweeps: boolean;
}) {
  const topologyKeys =
    params.topology_mode === "all"
      ? ["6pulse_typical", "12pulse_typical", "18pulse_typical", "afe_low_harm"]
      : [params.topology_mode];

  const filters = ["none", "tuned_5_7", "broadband_passive", "active_filter_like"];
  const tippingOpts = tippingOptionsFor(params.topology_mode);

  const sweepsBlock = params.enable_sweeps
    ? `sweeps:
  thdv_vs_sc_mva:
    enabled: true
    points: [20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 250.0, 500.0]
  tipping_points:
    enabled: true
    grid: [10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 150, 250, 500]
    options:
${tippingOpts.map((o) => `      - "${o}"`).join("\n")}`
    : `sweeps:
  thdv_vs_sc_mva:
    enabled: false
    points: [20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 250.0, 500.0]
  tipping_points:
    enabled: false
    grid: [10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100, 150, 250, 500]
    options:
${tippingOpts.map((o) => `      - "${o}"`).join("\n")}`;

  return `site:
  vll_v: ${yamlNumber(params.vll_v)}
  frequency_hz: ${yamlNumber(params.frequency_hz)}

load:
  demand_kw: ${yamlNumber(params.demand_kw)}
  load_pu: ${yamlNumber(params.load_pu)}
  pf_displacement: ${yamlNumber(params.pf_displacement)}
  efficiency: ${yamlNumber(params.efficiency)}
  kw_is_output: ${params.kw_is_output ? "true" : "false"}

grid:
  sc_mva: ${yamlNumber(params.sc_mva)}
  z_exp: ${yamlNumber(params.z_exp)}

limits:
  thdv_limit_pct: ${yamlNumber(params.thdv_limit_pct)}

scenario_space:
  topology_keys: [${topologyKeys.join(", ")}]
  filters: [${filters.join(", ")}]
  per_topology_filter_map:
    afe_low_harm: [none]

report:
  enabled: true
  report_name: "UPS Harmonics & Power Quality Screening Report"

${sweepsBlock}

tool:
  name: ups-pq-analyzer
  version: 0.1.0
  commit: "UI"
  engine_frozen: true
`;
}

export function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabKey>("run-analysis");

  const [results, setResults] = useState<ResultsWithArtifacts | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [fileName, setFileName] = useState<string>();
  const [error, setError] = useState<string>();
  const [runId, setRunId] = useState<string>();

  // Collapsible sidebar (desktop) + drawer (mobile)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [selectedPresetKey, setSelectedPresetKey] = useState<string>(
    PRESETS[0]?.key ?? ""
  );

  const [vllV, setVllV] = useState(415.0);
  const [freqHz, setFreqHz] = useState(60.0);
  const [demandKw, setDemandKw] = useState(1000.0);
  const [loadPu, setLoadPu] = useState(0.6);
  const [pfDisp, setPfDisp] = useState(0.99);
  const [eff, setEff] = useState(0.96);
  const [kwIsOutput, setKwIsOutput] = useState(true);
  const [scMva, setScMva] = useState(50.0);
  const [zExp, setZExp] = useState(1.0);
  const [thdvLimit, setThdvLimit] = useState(5.0);
  const [topologyMode, setTopologyMode] = useState<TopologyMode>("all");
  const [enableSweeps, setEnableSweeps] = useState(true);

  const selectedPreset = useMemo(() => {
    return PRESETS.find((p) => p.key === selectedPresetKey) ?? PRESETS[0];
  }, [selectedPresetKey]);

  const applyPreset = (p: Preset) => {
    setVllV(p.values.vllV);
    setFreqHz(p.values.freqHz);
    setDemandKw(p.values.demandKw);
    setLoadPu(p.values.loadPu);
    setPfDisp(p.values.pfDisp);
    setEff(p.values.eff);
    setKwIsOutput(p.values.kwIsOutput);
    setScMva(p.values.scMva);
    setZExp(p.values.zExp);
    setThdvLimit(p.values.thdvLimit);
    setTopologyMode(p.values.topologyMode);
    setEnableSweeps(p.values.enableSweeps);
  };

  const configYamlPreview = useMemo(() => {
    return buildConfigYaml({
      vll_v: vllV,
      frequency_hz: freqHz,
      demand_kw: demandKw,
      load_pu: loadPu,
      pf_displacement: pfDisp,
      efficiency: eff,
      kw_is_output: kwIsOutput,
      sc_mva: scMva,
      z_exp: zExp,
      thdv_limit_pct: thdvLimit,
      topology_mode: topologyMode,
      enable_sweeps: enableSweeps,
    });
  }, [
    vllV,
    freqHz,
    demandKw,
    loadPu,
    pfDisp,
    eff,
    kwIsOutput,
    scMva,
    zExp,
    thdvLimit,
    topologyMode,
    enableSweeps,
  ]);

  const handleFileLoad = async (file: File) => {
    setIsLoading(true);
    setError(undefined);
    setFileName(file.name);

    try {
      const text = await file.text();
      const data = JSON.parse(text) as ResultsWithArtifacts;
      setResults(data);
      setRunId(undefined);
      setActiveTab("results");
    } catch (err) {
      setError("Failed to parse JSON file. Please check the file format.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadSample = () => {
    setFileName("sample_results.json");
    setError(undefined);
    setResults(mockResults as ResultsWithArtifacts);
    setRunId(undefined);
    setActiveTab("results");
  };

  const handleDownloadResults = () => {
    if (!results) return;
    const blob = new Blob([JSON.stringify(results, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "results.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleOpenReport = () => {
    const r: any = results;
    const apiReportUrl = getApiUrl(r?.api_artifacts?.report_html_url);
    if (apiReportUrl) {
      window.open(apiReportUrl, "_blank");
      return;
    }

    if (!r?.artifacts?.report_html) return;
    const blob = new Blob([r.artifacts.report_html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
  };

  const handleRunAnalysis = async () => {
    setIsLoading(true);
    setError(undefined);

    try {
      const yamlText = configYamlPreview;
      const blob = new Blob([yamlText], { type: "text/yaml" });
      const file = new File([blob], "config.yaml", { type: "text/yaml" });

      const form = new FormData();
      form.append("config", file);

      const resp = await fetch(`${BACKEND_BASE_URL}/api/analyze`, {
        method: "POST",
        body: form,
      });

      const hdrRunId = resp.headers.get("x-run-id") ?? undefined;
      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        throw new Error(
          `Backend returned ${resp.status} ${resp.statusText}${
            text ? `: ${text}` : ""
          }`
        );
      }

      const data = (await resp.json()) as ResultsWithArtifacts;
      setResults(data);
      setRunId(hdrRunId);
      setFileName("api_results.json");
      setActiveTab("results");
      setSidebarOpen(false);
    } catch (e: any) {
      console.error(e);
      setError(e?.message ?? "Failed to run analysis.");
    } finally {
      setIsLoading(false);
    }
  };

  const normalized = useMemo(() => {
    if (!results) return null;
    const r: any = results;

    const recommended = r.executive_summary?.recommended_option ?? "—";
    const thdvLimitPct = r.executive_summary?.voltage_thdv_limit_percent ?? 5.0;
    const thdvValuePct = r.executive_summary?.voltage_thdv_percent;
    const thdvPass = r.executive_summary?.voltage_pass;

    const tddLimitPct = r.executive_summary?.current_tdd_limit_percent ?? 8.0;
    const tddValuePct = r.executive_summary?.current_tdd_percent;
    const tddPass = r.executive_summary?.current_practical_pass;

    const riskV = r.executive_summary?.risk_voltage ?? "—";
    const riskI = r.executive_summary?.risk_current ?? "—";
    const iscIl = r.executive_summary?.isc_over_il;
    const worstH = r.executive_summary?.worst_harmonic ?? undefined;
    const keyTakeaways = Array.isArray(r.executive_summary?.key_takeaways)
      ? r.executive_summary.key_takeaways
      : [];

    const reportUrl = getApiUrl(r.api_artifacts?.report_html_url);
    const resultsUrl = getApiUrl(r.api_artifacts?.results_url);

    const plots: { name: string; url: string }[] = Array.isArray(
      r.api_artifacts?.plots
    )
      ? r.api_artifacts.plots
          .filter((p: any) => p?.url)
          .map((p: any) => ({
            name: String(p.name ?? "plot"),
            url: String(p.url),
          }))
      : [];

    const raw: { name: string; url: string }[] = Array.isArray(r.api_artifacts?.raw)
      ? r.api_artifacts.raw
          .filter((p: any) => p?.url)
          .map((p: any) => ({
            name: String(p.name ?? "raw"),
            url: String(p.url),
          }))
      : [];

    const thdvSeriesPoints = toChartPoints(r.series?.thdv_vs_sc_mva?.points);

    return {
      recommended,
      thdvLimitPct: Number(thdvLimitPct),
      thdvValuePct: thdvValuePct !== undefined ? Number(thdvValuePct) : undefined,
      thdvPass: thdvPass !== undefined ? Boolean(thdvPass) : undefined,
      tddLimitPct: Number(tddLimitPct),
      tddValuePct: tddValuePct !== undefined ? Number(tddValuePct) : undefined,
      tddPass: tddPass !== undefined ? Boolean(tddPass) : undefined,
      riskV,
      riskI,
      iscIl: iscIl !== undefined ? Number(iscIl) : undefined,
      worstH,
      keyTakeaways,
      reportUrl,
      resultsUrl,
      plots,
      raw,
      thdvSeriesPoints,
    };
  }, [results]);

  const hasResults = !!results;
  const summaryTitleSplit = (normalized?.recommended ?? "").split(" - ");

  const desktopAsideWidth = sidebarCollapsed ? "lg:w-20" : "lg:w-72";

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Mobile drawer sidebar */}
      {sidebarOpen ? (
        <div className="lg:hidden fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[18rem] max-w-[85vw] bg-sidebar p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold text-sidebar-foreground flex items-center gap-2">
                <PanelLeft className="h-4 w-4 text-sidebar-primary" />
                Menu
              </div>
              <Button
                variant="outline"
                size="icon"
                className="bg-sidebar-accent border-sidebar-border text-sidebar-foreground hover:bg-sidebar-accent/80"
                onClick={() => setSidebarOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <LoadResultsPanel
              onFileLoad={handleFileLoad}
              onLoadSample={handleLoadSample}
              generatedTime={results?.generated_utc}
              isLoading={isLoading}
              fileName={fileName}
            />
          </div>
        </div>
      ) : null}

      {/* Desktop sidebar */}
      <aside
        className={[
          "hidden lg:block bg-sidebar p-4 lg:min-h-screen shrink-0 transition-[width] duration-200 ease-in-out",
          desktopAsideWidth,
        ].join(" ")}
      >
        <div className={sidebarCollapsed ? "overflow-hidden" : ""}>
          <LoadResultsPanel
            onFileLoad={handleFileLoad}
            onLoadSample={handleLoadSample}
            generatedTime={results?.generated_utc}
            isLoading={isLoading}
            fileName={fileName}
          />
        </div>
      </aside>

      <main className="flex-1 p-4 lg:p-6 overflow-x-hidden">
        {/* Top controls row: consistent toggles for desktop + mobile */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open sidebar"
            >
              <PanelLeft className="h-4 w-4" />
            </Button>

            <Button
              variant="outline"
              size="icon"
              className="hidden lg:inline-flex"
              onClick={() => setSidebarCollapsed((v) => !v)}
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {sidebarCollapsed ? (
                <PanelLeft className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </Button>

            {runId ? (
              <span className="hidden sm:inline text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
                Run: {runId}
              </span>
            ) : null}
          </div>
        </div>

        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as TabKey)}
          className="space-y-6"
        >
          <TabsList className="bg-muted">
            <TabsTrigger value="results" className="gap-2">
              <Activity className="h-4 w-4" />
              Results
            </TabsTrigger>
            <TabsTrigger value="run-analysis" className="gap-2">
              <Play className="h-4 w-4" />
              Run Analysis
            </TabsTrigger>
          </TabsList>

          <TabsContent value="results" className="space-y-6">
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {!hasResults ? (
              <Card className="border-dashed border-2">
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                  <FileText className="h-12 w-12 text-muted-foreground/50 mb-4" />
                  <h3 className="text-lg font-semibold text-foreground mb-2">
                    No Results Loaded
                  </h3>
                  <p className="text-muted-foreground max-w-sm">
                    Run an analysis or upload a JSON results file.
                  </p>
                  <div className="mt-6">
                    <Button
                      variant="outline"
                      className="gap-2"
                      onClick={() => setActiveTab("run-analysis")}
                    >
                      <Play className="h-4 w-4" />
                      Go to Run Analysis
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <>
                <section>
                  <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Target className="h-5 w-5 text-primary" />
                    Executive Summary
                  </h2>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
                    <SummaryCard
                      title="Recommended"
                      value={summaryTitleSplit[0] ?? normalized?.recommended ?? "—"}
                      subtitle={summaryTitleSplit[1] ?? undefined}
                      icon={CheckCircle2}
                      className="sm:col-span-2"
                    />
                    <SummaryCard
                      title="THDv Limit"
                      value={`${normalized?.thdvLimitPct ?? 5}%`}
                      status={
                        normalized?.thdvPass === undefined
                          ? undefined
                          : normalized.thdvPass
                          ? "PASS"
                          : "FAIL"
                      }
                      icon={Zap}
                    />
                    <SummaryCard
                      title="TDD Limit"
                      value={`${normalized?.tddLimitPct ?? 8}%`}
                      status={
                        normalized?.tddPass === undefined
                          ? undefined
                          : normalized.tddPass
                          ? "PASS"
                          : "FAIL"
                      }
                      icon={Zap}
                    />
                    <SummaryCard
                      title="Risk Voltage"
                      value={String(normalized?.riskV ?? "—")}
                      status={String(normalized?.riskV ?? "—")}
                      icon={AlertTriangle}
                    />
                    <SummaryCard
                      title="Risk Current"
                      value={String(normalized?.riskI ?? "—")}
                      status={String(normalized?.riskI ?? "—")}
                      icon={AlertTriangle}
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    <SummaryCard
                      title="Isc/IL Ratio"
                      value={
                        normalized?.iscIl !== undefined
                          ? normalized.iscIl.toFixed(1)
                          : "—"
                      }
                      subtitle="Short circuit to load ratio"
                      icon={Activity}
                    />
                    <SummaryCard
                      title="Worst Harmonic"
                      value={
                        normalized?.worstH === null ||
                        normalized?.worstH === undefined
                          ? "—"
                          : `${normalized.worstH}`
                      }
                      subtitle="Dominant harmonic order"
                      icon={Settings2}
                    />
                    <SummaryCard
                      title="THDv @ PCC"
                      value={
                        normalized?.thdvValuePct !== undefined
                          ? `${normalized.thdvValuePct.toFixed(2)}%`
                          : "—"
                      }
                      subtitle="Estimated voltage distortion"
                      icon={Zap}
                    />
                  </div>
                </section>

                <section>
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-semibold flex items-center gap-2">
                        <Lightbulb className="h-4 w-4 text-warning" />
                        Key Takeaways
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {(normalized?.keyTakeaways ?? []).map(
                          (takeaway: string, i: number) => (
                            <li
                              key={i}
                              className="flex items-start gap-2 text-sm"
                            >
                              <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
                              <span className="text-foreground">{takeaway}</span>
                            </li>
                          )
                        )}
                      </ul>
                    </CardContent>
                  </Card>
                </section>

                <section>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Inputs & Assumptions
                  </h2>
                  <KeyValueTable data={(results as any).inputs_assumptions} />
                </section>

                <section>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Top Scenarios Ranked
                  </h2>
                  <DataTable
                    columns={(results as any).tables.top_scenarios_ranked.columns}
                    rows={(results as any).tables.top_scenarios_ranked.rows}
                  />
                </section>

                <section>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Tipping Points - Min SSC Required
                  </h2>
                  <DataTable
                    columns={
                      (results as any).tables.tipping_points_min_ssc_required
                        .columns
                    }
                    rows={
                      (results as any).tables.tipping_points_min_ssc_required.rows
                    }
                  />
                </section>

                {normalized?.thdvSeriesPoints &&
                normalized.thdvSeriesPoints.length > 0 ? (
                  <section>
                    <h2 className="text-lg font-semibold text-foreground mb-4">
                      Analysis Plots
                    </h2>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <ThdvChart
                        points={normalized.thdvSeriesPoints}
                        thdvLimit={normalized.thdvLimitPct ?? 5}
                      />
                      {(normalized.plots ?? []).map((p) => (
                        <Card key={p.name}>
                          <CardContent className="p-4">
                            <img
                              src={getApiUrl(p.url)}
                              alt={p.name}
                              className="w-full rounded-lg"
                            />
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </section>
                ) : null}

                <section>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Downloads
                  </h2>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      onClick={handleDownloadResults}
                      variant="outline"
                      className="gap-2"
                    >
                      <Download className="h-4 w-4" />
                      Download results.json
                    </Button>

                    {normalized?.reportUrl ? (
                      <Button
                        onClick={handleOpenReport}
                        variant="outline"
                        className="gap-2"
                      >
                        <FileText className="h-4 w-4" />
                        Open report.html
                      </Button>
                    ) : null}

                    {normalized?.resultsUrl ? (
                      <a
                        href={normalized.resultsUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
                      >
                        <LinkIcon className="h-4 w-4" />
                        Open results.json (API)
                      </a>
                    ) : null}
                  </div>
                </section>

                <section>
                  <Alert className="bg-muted/50 border-muted">
                    <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                    <AlertDescription className="text-xs text-muted-foreground">
                      {(results as any).disclaimer}
                    </AlertDescription>
                  </Alert>
                </section>
              </>
            )}
          </TabsContent>

          <TabsContent value="run-analysis" className="space-y-6">
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    <Play className="h-5 w-5 text-primary" />
                    Run Analysis (IEEE-519 Screening)
                  </span>
                </CardTitle>
              </CardHeader>

              <CardContent className="space-y-6">
                <Card className="bg-muted/30">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-semibold">Presets</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                      <Field label="Preset">
                        <SelectInput
                          value={selectedPresetKey}
                          onChange={(e) => setSelectedPresetKey(e.target.value)}
                        >
                          {PRESETS.map((p) => (
                            <option key={p.key} value={p.key}>
                              {p.label}
                            </option>
                          ))}
                        </SelectInput>
                      </Field>

                      <div className="md:col-span-2 flex flex-wrap gap-3 items-center">
                        <Button
                          type="button"
                          className="gap-2"
                          onClick={() =>
                            selectedPreset && applyPreset(selectedPreset)
                          }
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          Apply Preset
                        </Button>

                        {selectedPreset?.description ? (
                          <span className="text-sm text-muted-foreground">
                            {selectedPreset.description}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  <Field label="VLL (V)" hint="e.g., 415">
                    <TextInput
                      type="number"
                      step="0.1"
                      value={vllV}
                      onChange={(e) => setVllV(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="Frequency (Hz)" hint="60 in US">
                    <TextInput
                      type="number"
                      step="0.1"
                      value={freqHz}
                      onChange={(e) => setFreqHz(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="Demand (kW)" hint="facility / UPS demand basis">
                    <TextInput
                      type="number"
                      step="1"
                      value={demandKw}
                      onChange={(e) => setDemandKw(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="Load pu" hint="0–1 (fraction of demand)">
                    <TextInput
                      type="number"
                      step="0.01"
                      value={loadPu}
                      onChange={(e) => setLoadPu(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="PF (displacement)" hint="e.g., 0.99">
                    <TextInput
                      type="number"
                      step="0.01"
                      value={pfDisp}
                      onChange={(e) => setPfDisp(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="Efficiency" hint="e.g., 0.96">
                    <TextInput
                      type="number"
                      step="0.01"
                      value={eff}
                      onChange={(e) => setEff(Number(e.target.value))}
                    />
                  </Field>

                  <Field
                    label="PCC Short-Circuit Strength (SC MVA)"
                    hint="utility stiffness"
                  >
                    <TextInput
                      type="number"
                      step="0.1"
                      value={scMva}
                      onChange={(e) => setScMva(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="Impedance exponent (z_exp)" hint="typ. 1.0">
                    <TextInput
                      type="number"
                      step="0.1"
                      value={zExp}
                      onChange={(e) => setZExp(Number(e.target.value))}
                    />
                  </Field>

                  <Field label="THDv limit (%)" hint="IEEE-519 default 5%">
                    <TextInput
                      type="number"
                      step="0.1"
                      value={thdvLimit}
                      onChange={(e) => setThdvLimit(Number(e.target.value))}
                    />
                  </Field>

                  <Field
                    label="Topology set"
                    hint="controls which topology presets are evaluated"
                  >
                    <SelectInput
                      value={topologyMode}
                      onChange={(e) =>
                        setTopologyMode(e.target.value as TopologyMode)
                      }
                    >
                      <option value="all">All (6/12/18/AFE)</option>
                      <option value="afe_low_harm">AFE (low harmonics)</option>
                      <option value="18pulse_typical">18-pulse (typical)</option>
                      <option value="12pulse_typical">12-pulse (typical)</option>
                      <option value="6pulse_typical">6-pulse (typical)</option>
                    </SelectInput>
                  </Field>

                  <Field label="Demand basis" hint="kW is output?">
                    <SelectInput
                      value={kwIsOutput ? "true" : "false"}
                      onChange={(e) => setKwIsOutput(e.target.value === "true")}
                    >
                      <option value="true">
                        kW is output (kw_is_output=true)
                      </option>
                      <option value="false">kW is input (kw_is_output=false)</option>
                    </SelectInput>
                  </Field>

                  <Field label="Sweeps / plots" hint="thdv_vs_sc_mva + tipping points">
                    <SelectInput
                      value={enableSweeps ? "true" : "false"}
                      onChange={(e) => setEnableSweeps(e.target.value === "true")}
                    >
                      <option value="true">Enabled</option>
                      <option value="false">Disabled</option>
                    </SelectInput>
                  </Field>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    onClick={handleRunAnalysis}
                    className="gap-2"
                    disabled={isLoading}
                  >
                    <Play className="h-4 w-4" />
                    {isLoading ? "Running..." : "Generate Screening Report"}
                  </Button>

                  <Button
                    type="button"
                    variant="outline"
                    className="gap-2"
                    onClick={() => {
                      const blob = new Blob([configYamlPreview], {
                        type: "text/yaml",
                      });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "config.yaml";
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    <Download className="h-4 w-4" />
                    Download config.yaml
                  </Button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <Card className="bg-muted/30">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-semibold">
                        Config Preview (YAML)
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <pre className="text-xs overflow-auto max-h-[360px] whitespace-pre-wrap text-foreground">
                        {configYamlPreview}
                      </pre>
                    </CardContent>
                  </Card>

                  <Card className="bg-muted/30">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-semibold">
                        Artifacts
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                      After a run, artifacts will appear in the Results tab as
                      API-backed links and thumbnails.
                    </CardContent>
                  </Card>
                </div>

                <Alert className="bg-muted/50 border-muted">
                  <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                  <AlertDescription className="text-xs text-muted-foreground">
                    This tool provides a deterministic IEEE-519-oriented screening
                    result. Final compliance depends on site-specific studies and
                    measured conditions.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
