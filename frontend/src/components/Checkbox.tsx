import { InputHTMLAttributes, forwardRef } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

export const Checkbox = forwardRef<HTMLInputElement, Props>(({ className, ...rest }, ref) => {
  // Box and icon are both direct siblings of the input (not nested inside
  // one another) -- Tailwind's peer-* variant only matches siblings of
  // the peer element, not descendants of a sibling, so nesting the icon
  // inside the box span would silently never receive peer-checked.
  return (
    <span className={cn("relative inline-flex h-5 w-5 shrink-0", className)}>
      <input ref={ref} type="checkbox" className="peer absolute inset-0 h-full w-full cursor-pointer opacity-0" {...rest} />
      <span
        className={cn(
          "pointer-events-none absolute inset-0 rounded-md border border-border bg-surface-2 transition-colors duration-150",
          "peer-checked:border-accent peer-checked:bg-accent",
          "peer-focus-visible:ring-2 peer-focus-visible:ring-accent/30",
          "peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        )}
      />
      <Check className="pointer-events-none absolute inset-0 m-auto h-3.5 w-3.5 scale-0 text-white transition-transform duration-150 peer-checked:scale-100" />
    </span>
  );
});
Checkbox.displayName = "Checkbox";
