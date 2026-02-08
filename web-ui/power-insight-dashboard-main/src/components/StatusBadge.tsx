import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: "PASS" | "FAIL" | "LOW" | "MEDIUM" | "HIGH";
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const getStatusStyles = () => {
    switch (status) {
      case "PASS":
      case "LOW":
        return "bg-success/15 text-success border-success/30";
      case "FAIL":
      case "HIGH":
        return "bg-destructive/15 text-destructive border-destructive/30";
      case "MEDIUM":
        return "bg-warning/15 text-warning border-warning/30";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold border uppercase tracking-wide",
        getStatusStyles(),
        className
      )}
    >
      {status}
    </span>
  );
}
