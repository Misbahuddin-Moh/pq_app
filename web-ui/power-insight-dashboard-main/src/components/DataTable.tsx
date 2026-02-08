import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "./StatusBadge";
import { cn } from "@/lib/utils";

interface DataTableProps {
  columns: string[];
  rows: (string | number)[][];
  className?: string;
}

export function DataTable({ columns, rows, className }: DataTableProps) {
  const renderCell = (value: string | number, columnName: string) => {
    const strValue = String(value);
    
    // Check if it's a status column
    if (strValue === "PASS" || strValue === "FAIL") {
      return <StatusBadge status={strValue} />;
    }
    
    // Check if it's a risk column
    if (strValue === "LOW" || strValue === "MEDIUM" || strValue === "HIGH") {
      return <StatusBadge status={strValue} />;
    }
    
    // Format numbers
    if (typeof value === "number") {
      // Check if it looks like a percentage column
      if (columnName.includes("%") || columnName.toLowerCase().includes("margin")) {
        return (
          <span className={cn(
            "font-mono",
            value < 0 ? "text-destructive" : ""
          )}>
            {value.toFixed(1)}%
          </span>
        );
      }
      return <span className="font-mono">{value.toLocaleString()}</span>;
    }
    
    return strValue;
  };

  return (
    <div className={cn("rounded-lg border bg-card overflow-hidden", className)}>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              {columns.map((column, i) => (
                <TableHead 
                  key={i} 
                  className="text-xs font-semibold text-foreground uppercase tracking-wide whitespace-nowrap"
                >
                  {column}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, rowIndex) => (
              <TableRow key={rowIndex} className="hover:bg-muted/30">
                {row.map((cell, cellIndex) => (
                  <TableCell 
                    key={cellIndex} 
                    className="text-sm whitespace-nowrap"
                  >
                    {renderCell(cell, columns[cellIndex])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
