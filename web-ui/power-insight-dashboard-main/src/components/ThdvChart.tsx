import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import type { SeriesPoint } from "@/types/results";

interface ThdvChartProps {
  points: SeriesPoint[];
  thdvLimit: number;
}

export function ThdvChart({ points, thdvLimit }: ThdvChartProps) {
  const data = points.map(p => ({
    ssc: p.x,
    thdv: p.y
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">THDv vs Short Circuit MVA</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis 
                dataKey="ssc" 
                label={{ value: 'SSC (MVA)', position: 'bottom', offset: -5 }}
                className="text-xs"
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
              />
              <YAxis 
                label={{ value: 'THDv (%)', angle: -90, position: 'insideLeft' }}
                className="text-xs"
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
                domain={[0, 'auto']}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px'
                }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'THDv']}
                labelFormatter={(label) => `SSC: ${label} MVA`}
              />
              <ReferenceLine 
                y={thdvLimit} 
                stroke="hsl(var(--destructive))" 
                strokeDasharray="5 5"
                label={{ 
                  value: `Limit: ${thdvLimit}%`, 
                  position: 'right',
                  fill: 'hsl(var(--destructive))',
                  fontSize: 11
                }}
              />
              <Line 
                type="monotone" 
                dataKey="thdv" 
                stroke="hsl(var(--primary))" 
                strokeWidth={2}
                dot={{ fill: 'hsl(var(--primary))', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, fill: 'hsl(var(--accent))' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
