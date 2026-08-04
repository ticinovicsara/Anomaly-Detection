import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  message,
  action,
}: {
  icon: LucideIcon;
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <div className="rounded-2xl bg-surface-2 p-3 text-accent/70">
        <Icon className="h-6 w-6" />
      </div>
      <p className="text-sm font-medium text-text">{title}</p>
      {message && <p className="max-w-xs text-xs text-muted">{message}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
