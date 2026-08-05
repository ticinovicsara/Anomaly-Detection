import { ButtonHTMLAttributes, ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-hover shadow-soft hover:shadow-glow disabled:bg-accent/50",
  secondary:
    "bg-surface-2 text-text border border-border hover:border-accent/50 hover:bg-surface",
  ghost: "text-muted hover:text-text hover:bg-surface-2",
  danger: "bg-danger text-white hover:bg-danger/90",
};

const sizes: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm rounded-lg",
  md: "px-4 py-2 text-sm rounded-xl",
  lg: "px-5 py-2.5 text-base rounded-xl",
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  icon,
  children,
  className,
  disabled,
  ...rest
}: Props) {
  const reduceMotion = useReducedMotion();
  const isDisabled = disabled || loading;
  return (
    <motion.button
      // framer-motion's event typings conflict with a few native handlers
      // (onDrag*, onAnimationStart/End) that this app never passes through
      // Button -- safe to widen at the spread boundary.
      {...(rest as Omit<typeof rest, "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart">)}
      disabled={isDisabled}
      whileTap={isDisabled || reduceMotion ? undefined : { scale: 0.96 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-[background-color,box-shadow,border-color] duration-150 ease-out-strong disabled:cursor-not-allowed disabled:opacity-70",
        variants[variant],
        sizes[size],
        className
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </motion.button>
  );
}
