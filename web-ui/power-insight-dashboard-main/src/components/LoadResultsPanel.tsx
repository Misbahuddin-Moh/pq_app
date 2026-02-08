import { useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Upload,
  FileJson,
  Clock,
  Loader2,
  Download,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";

type DownloadItem = {
  label: string;
  url: string;
};

type RunItem = {
  run_id: string;
  generated_utc?: string;
  downloads: DownloadItem[];
};

interface LoadResultsPanelProps {
  onFileLoad: (file: File) => void;
  onLoadSample: () => void;
  generatedTime?: string;
  isLoading?: boolean;
  fileName?: string;

  // Optional: zip pack endpoint (if/when backend provides it)
  downloadZipUrl?: string;
  downloadZipLabel?: string;

  // Optional: show downloads for current + recent runs
  currentRun?: RunItem;
  recentRuns?: RunItem[];
}

export function LoadResultsPanel({
  onFileLoad,
  onLoadSample,
  generatedTime,
  isLoading,
  fileName,
  downloadZipUrl,
  downloadZipLabel,
  currentRun,
  recentRuns,
}: LoadResultsPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileLoad(file);
  };

  const formatTime = (utcString: string) => {
    try {
      const date = new Date(utcString);
      return date.toLocaleString();
    } catch {
      return utcString;
    }
  };

  const openUrl = (url: string) => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const renderRunDownloads = (run: RunItem) => {
    return (
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs font-medium text-sidebar-foreground truncate">
              Run: {run.run_id}
            </div>
            {run.generated_utc ? (
              <div className="text-[11px] text-sidebar-foreground/70 truncate">
                {formatTime(run.generated_utc)}
              </div>
            ) : null}
          </div>
        </div>

        <div className="space-y-1">
          {run.downloads.map((d) => (
            <button
              key={`${run.run_id}:${d.label}`}
              type="button"
              onClick={() => openUrl(d.url)}
              className={cn(
                "w-full flex items-center justify-between gap-2 rounded-md",
                "px-2 py-1.5 text-left text-xs",
                "bg-sidebar-accent border border-sidebar-border",
                "text-sidebar-foreground hover:bg-sidebar-accent/80"
              )}
            >
              <span className="min-w-0 truncate">{d.label}</span>
              <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-70" />
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <Card className="bg-sidebar border-sidebar-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold text-sidebar-foreground flex items-center gap-2">
          <FileJson className="h-4 w-4 text-sidebar-primary" />
          Load Results
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <input
          type="file"
          ref={fileInputRef}
          accept=".json"
          onChange={handleFileChange}
          className="hidden"
        />

        <Button
          variant="outline"
          className={cn(
            "w-full justify-start gap-2 bg-sidebar-accent border-sidebar-border",
            "text-sidebar-foreground hover:bg-sidebar-accent/80 hover:text-sidebar-foreground",
            "min-w-0"
          )}
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
          <span className="min-w-0 truncate">Upload JSON File</span>
        </Button>

        <Button
          variant="secondary"
          className={cn(
            "w-full bg-sidebar-primary text-sidebar-primary-foreground",
            "hover:bg-sidebar-primary/90",
            "min-w-0"
          )}
          onClick={onLoadSample}
          disabled={isLoading}
        >
          <span className="min-w-0 truncate">Load Sample Data</span>
        </Button>

        {/* Zip pack button (only show if provided, so we never render a dead/unclickable button) */}
        {downloadZipUrl ? (
          <Button
            variant="outline"
            className={cn(
              "w-full justify-start gap-2 bg-sidebar-accent border-sidebar-border",
              "text-sidebar-foreground hover:bg-sidebar-accent/80 hover:text-sidebar-foreground",
              "min-w-0"
            )}
            onClick={() => openUrl(downloadZipUrl)}
            disabled={isLoading}
            title="Download report pack (HTML + PNG plots + results.json)"
          >
            <Download className="h-4 w-4 shrink-0" />
            <span className="min-w-0 truncate">
              {downloadZipLabel ?? "Download report pack (.zip)"}
            </span>
          </Button>
        ) : null}

        {fileName && (
          <div className="pt-2 border-t border-sidebar-border">
            <p className="text-xs text-sidebar-foreground/70 truncate">
              <span className="font-medium">File:</span> {fileName}
            </p>
          </div>
        )}

        {generatedTime && (
          <div className="flex items-center gap-1.5 text-xs text-sidebar-foreground/70">
            <Clock className="h-3 w-3" />
            <span className="truncate">{formatTime(generatedTime)}</span>
          </div>
        )}

        {/* Downloads for current run */}
        {currentRun?.downloads?.length ? (
          <div className="pt-3 border-t border-sidebar-border space-y-2">
            <div className="text-xs font-semibold text-sidebar-foreground flex items-center gap-2">
              <Download className="h-3.5 w-3.5 text-sidebar-primary" />
              Downloads (current)
            </div>
            {renderRunDownloads(currentRun)}
          </div>
        ) : null}

        {/* Recent runs */}
        {recentRuns?.length ? (
          <div className="pt-3 border-t border-sidebar-border space-y-3">
            <div className="text-xs font-semibold text-sidebar-foreground flex items-center gap-2">
              <ExternalLink className="h-3.5 w-3.5 text-sidebar-primary" />
              Recent runs
            </div>

            <div className="space-y-3">
              {recentRuns.slice(0, 5).map((r) => (
                <div key={r.run_id} className="space-y-2">
                  {renderRunDownloads(r)}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
