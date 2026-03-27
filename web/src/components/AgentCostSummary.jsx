export function formatCost(dollars) {
  if (dollars >= 1) return `$${dollars.toFixed(2)}`;
  const cents = dollars * 100;
  return `${cents.toFixed(1)}¢`;
}

export function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const totalMins = Math.floor(secs / 60);
  const remSecs = Math.round(secs % 60);
  if (totalMins < 60) return `${totalMins}m ${remSecs}s`;
  const hrs = Math.floor(totalMins / 60);
  const remMins = totalMins % 60;
  if (remMins === 0) return `${hrs}hr`;
  return `${hrs}hr ${remMins}m`;
}

export default function AgentCostSummary({ cost, timeMs, className = "" }) {
  const hasCost = cost != null && cost > 0;
  const hasTime = timeMs != null && timeMs > 0;
  if (!hasCost && !hasTime) return null;

  return (
    <div
      className={`flex items-center gap-1 text-xs text-slate-400 ${className}`}
    >
      {hasCost && (
        <span>
          <span className="text-slate-500 font-medium">
            {formatCost(Number(cost))}
          </span>{" "}
          spent
        </span>
      )}
      {hasCost && hasTime && <span className="w-px h-2.5 bg-slate-200" />}
      {hasTime && (
        <span>
          <span className="text-slate-500 font-medium">
            {formatDuration(timeMs)}
          </span>{" "}
          taken
        </span>
      )}
    </div>
  );
}
