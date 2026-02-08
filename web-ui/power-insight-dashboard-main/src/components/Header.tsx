import { Zap } from "lucide-react";

export function Header() {
  return (
    <header className="bg-sidebar border-b border-sidebar-border px-4 py-3 lg:px-6">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
          <Zap className="h-6 w-6 text-primary-foreground" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-sidebar-foreground">
            UPS Harmonics & Power Quality Analyzer
          </h1>
          <p className="text-xs text-sidebar-foreground/70">
            IEEE-519-oriented screening tool for data centers
          </p>
        </div>
      </div>
    </header>
  );
}
