import { cn } from "@/lib/utils";

interface KeyValueTableProps {
  data: Record<string, string | number>;
  className?: string;
}

export function KeyValueTable({ data, className }: KeyValueTableProps) {
  const entries = Object.entries(data);
  
  return (
    <div className={cn("rounded-lg border bg-card overflow-hidden", className)}>
      <div className="overflow-x-auto">
        <table className="w-full">
          <tbody>
            {entries.map(([key, value], index) => (
              <tr 
                key={key} 
                className={cn(
                  "border-b last:border-b-0",
                  index % 2 === 0 ? "bg-card" : "bg-muted/30"
                )}
              >
                <td className="px-4 py-2.5 text-sm font-medium text-muted-foreground w-1/2">
                  {key}
                </td>
                <td className="px-4 py-2.5 text-sm font-semibold text-foreground font-mono">
                  {value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
