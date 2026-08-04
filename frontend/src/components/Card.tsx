import { HTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/cn";
import { useCountUp } from "../hooks/useCountUp";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
  children: ReactNode;
}

export function Card({ hoverable, className, children, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={cn(
        "rounded-2xl border border-border bg-surface p-6 shadow-soft transition-[transform,box-shadow,border-color] duration-200 ease-out-strong",
        hoverable && "hover:border-accent/40 hover:shadow-glow hover:-translate-y-0.5",
        className
      )}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: ReactNode;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const toneClasses = {
    default: "text-text",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
  }[tone];

  const numericValue = typeof value === "number" ? value : null;
  const animatedValue = useCountUp(numericValue ?? 0);
  const displayValue = numericValue !== null ? animatedValue : value;

  return (
    <Card hoverable>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted">{label}</p>
          <p className={cn("mt-2 text-3xl font-semibold tracking-tight tabular-nums", toneClasses)}>
            {displayValue}
          </p>
          {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
        </div>
        {icon && (
          <div className="rounded-xl bg-surface-2 p-2.5 text-accent">{icon}</div>
        )}
      </div>
    </Card>
  );
}
