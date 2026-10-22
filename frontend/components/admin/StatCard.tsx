interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: "teal" | "green" | "blue" | "orange" | "red";
}

const colorClasses = {
  teal: "bg-teal/10 text-teal border-teal",
  green: "bg-green-100 text-green-700 border-green-300",
  blue: "bg-blue-100 text-blue-700 border-blue-300",
  orange: "bg-orange-100 text-orange-700 border-orange-300",
  red: "bg-red-100 text-red-700 border-red-300",
};

export function StatCard({ label, value, subtitle, color = "teal" }: StatCardProps) {
  const colorClass = colorClasses[color];

  return (
    <div className={`rounded-lg border-2 ${colorClass} p-6`}>
      <p className="text-sm font-medium opacity-80">{label}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
      {subtitle && <p className="mt-1 text-xs opacity-70">{subtitle}</p>}
    </div>
  );
}
