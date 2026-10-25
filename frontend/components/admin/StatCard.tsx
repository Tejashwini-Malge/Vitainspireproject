import { cn } from "@/components/ui/cn";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: "teal" | "green" | "blue" | "orange" | "red";
}

// Legacy prop names (green/blue/orange/red) are kept so existing call sites don't need to
// change; they now map onto the ledger status tokens instead of bare Tailwind colors.
const colorClasses: Record<NonNullable<StatCardProps["color"]>, string> = {
  teal: "bg-teal/10 text-teal border-teal/40",
  green: "bg-status-approved/10 text-status-approved border-status-approved/40",
  blue: "bg-navy/5 text-navy border-navy/30",
  orange: "bg-status-pending/10 text-status-pending border-status-pending/40",
  red: "bg-status-rejected/10 text-status-rejected border-status-rejected/40",
};

export function StatCard({ label, value, subtitle, color = "teal" }: StatCardProps) {
  const colorClass = colorClasses[color];

  return (
    <div
      className={cn(
        "rounded-sm border bg-[#FFFDF7] p-6 shadow-[0_1px_2px_rgba(42,43,38,0.05)]",
        colorClass,
      )}
    >
      <p className="font-mono text-xs uppercase tracking-[0.14em] opacity-80">{label}</p>
      <p className="mt-2 font-display text-3xl font-semibold">{value}</p>
      {subtitle && <p className="mt-1 text-xs opacity-70">{subtitle}</p>}
    </div>
  );
}
