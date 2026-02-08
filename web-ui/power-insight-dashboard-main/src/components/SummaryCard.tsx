import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "./StatusBadge";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface SummaryCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  status?: "PASS" | "FAIL" | "LOW" | "MEDIUM" | "HIGH";
  icon?: LucideIcon;
  className?: string;
}

export function SummaryCard({ 
  title, 
  value, 
  subtitle, 
  status, 
  icon: Icon,
  className 
}: SummaryCardProps) {
  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1 flex-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {title}
            </p>
            <p className="text-xl font-bold text-foreground leading-tight">
              {value}
            </p>
            {subtitle && (
              <p className="text-xs text-muted-foreground">
                {subtitle}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            {Icon && (
              <Icon className="h-5 w-5 text-muted-foreground/50" />
            )}
            {status && <StatusBadge status={status} />}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
