import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, Props>(
  ({ label, hint, error, className, id, ...rest }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-text">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={id}
          {...rest}
          className={cn(
            "w-full rounded-xl border border-border bg-surface-2 px-4 py-2.5 text-sm text-text placeholder:text-muted transition-[border-color,box-shadow] duration-150 ease-out",
            "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30",
            error && "border-danger focus:border-danger focus:ring-danger/30",
            className
          )}
        />
        {hint && !error && <p className="mt-1 text-xs text-muted">{hint}</p>}
        {error && <p className="mt-1 text-xs text-danger">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";
