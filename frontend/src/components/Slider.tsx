import { InputHTMLAttributes } from "react";
import { cn } from "../lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  formatter?: (v: number) => string;
}

export function Slider({
  label,
  value,
  min,
  max,
  step = 0.1,
  onChange,
  formatter,
  className,
}: Props) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className={cn("w-full", className)}>
      {label && (
        <div className="mb-2 flex items-center justify-between">
          <label className="text-sm font-medium text-text">{label}</label>
          <span className="rounded-md bg-surface-2 px-2 py-0.5 text-xs font-mono text-accent">
            {formatter ? formatter(value) : value}
          </span>
        </div>
      )}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={onChange}
        className="range-slider w-full"
        style={{
          background: `linear-gradient(to right, rgb(var(--accent)) 0%, rgb(var(--accent)) ${pct}%, rgb(var(--border)) ${pct}%, rgb(var(--border)) 100%)`,
        }}
      />
      <style>{`
        .range-slider {
          -webkit-appearance: none;
          appearance: none;
          height: 6px;
          border-radius: 9999px;
          outline: none;
        }
        .range-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          height: 18px;
          width: 18px;
          border-radius: 9999px;
          background: rgb(var(--accent));
          cursor: pointer;
          border: 3px solid rgb(var(--surface));
          box-shadow: 0 0 0 1px rgb(var(--border));
          transition: transform 0.15s;
        }
        .range-slider::-webkit-slider-thumb:hover { transform: scale(1.15); }
        .range-slider::-moz-range-thumb {
          height: 18px;
          width: 18px;
          border-radius: 9999px;
          background: rgb(var(--accent));
          cursor: pointer;
          border: 3px solid rgb(var(--surface));
          box-shadow: 0 0 0 1px rgb(var(--border));
        }
      `}</style>
    </div>
  );
}
