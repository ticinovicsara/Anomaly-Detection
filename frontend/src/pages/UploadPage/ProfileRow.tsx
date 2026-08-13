export function ProfileRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between rounded-lg px-3 py-2 hover:bg-surface-2/50">
      <div>
        <p className="text-xs text-muted">{label}</p>
        {hint && <p className="text-[10px] text-muted/70">{hint}</p>}
      </div>
      <span className="font-mono text-sm text-text">{value}</span>
    </div>
  );
}
