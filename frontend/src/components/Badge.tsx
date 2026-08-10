import { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "default" | "success" | "warning" | "danger" | "accent";

const tones: Record<Tone, string> = {
  default: "bg-surface-2 text-muted border-border",
  success: "bg-success/10 text-success border-success/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  danger: "bg-danger/10 text-danger border-danger/20",
  accent: "bg-accent/10 text-accent border-accent/20",
};

export function Badge({
  tone = "default",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone]
      )}
    >
      {children}
    </span>
  );
}

export function severityTone(severity: string): Tone {
  if (severity === "critical") return "danger";
  if (severity === "warning") return "warning";
  return "accent";
}

export function statusTone(status: string): Tone {
  if (status === "ready") return "success";
  if (status === "failed") return "danger";
  if (status === "training") return "warning";
  return "default";
}
