import { formatCost, formatDuration } from "./AgentCostSummary";

export default function ProjectAgentSummary({
  totalCost,
  totalAgentTimeMs,
  className = "",
}) {
  const hasCost = totalCost != null && totalCost > 0;
  const hasTime = totalAgentTimeMs != null && totalAgentTimeMs > 0;
  if (!hasCost && !hasTime) return null;

  return (
    <div className={`flex items-center gap-2.5 text-xs ${className}`}>
      {hasCost && (
        <span className="inline-flex items-center gap-1 text-slate-400">
          <span className="text-amber-500">$</span>
          <span className="text-slate-500 font-medium">
            {formatCost(Number(totalCost))}
          </span>
        </span>
      )}
      {hasCost && hasTime && <span className="w-px h-2.5 bg-slate-200" />}
      {hasTime && (
        <span className="inline-flex items-center gap-1 text-slate-400">
          <span className="text-indigo-400">⏱</span>
          <span className="text-slate-500 font-medium">
            {formatDuration(totalAgentTimeMs)}
          </span>
        </span>
      )}
    </div>
  );
}
