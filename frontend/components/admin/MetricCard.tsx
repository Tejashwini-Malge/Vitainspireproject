interface Metric {
  label: string;
  value: string | number;
}

interface MetricCardProps {
  title: string;
  metrics: Metric[];
}

export function MetricCard({ title, metrics }: MetricCardProps) {
  return (
    <div className="rounded-lg border-2 border-line bg-white p-6">
      <h3 className="mb-4 font-semibold text-navy">{title}</h3>
      <div className="space-y-3">
        {metrics.map((metric) => (
          <div key={metric.label} className="flex items-center justify-between">
            <span className="text-sm text-muted">{metric.label}</span>
            <span className="font-medium text-navy">{metric.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
