interface RiskBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

function riskTier(score: number): { label: string; bg: string; text: string; border: string } {
  if (score >= 75) return { label: "Critical", bg: "bg-red-50", text: "text-red-700", border: "border-red-200" };
  if (score >= 50) return { label: "High", bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" };
  if (score >= 25) return { label: "Medium", bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" };
  return { label: "Low", bg: "bg-teal-50", text: "text-teal-700", border: "border-teal-200" };
}

const SIZE_CLASSES = {
  sm: "text-xs px-1.5 py-0.5",
  md: "text-sm px-2 py-1",
  lg: "text-base px-3 py-1.5 font-semibold",
};

export function RiskBadge({ score, size = "md" }: RiskBadgeProps) {
  const tier = riskTier(score);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border ${tier.bg} ${tier.border} ${tier.text} ${SIZE_CLASSES[size]}`}
      title={`Risk score: ${Math.round(score)}`}
    >
      <span className="font-mono font-bold">{Math.round(score)}</span>
      <span className="opacity-75">{tier.label}</span>
    </span>
  );
}
