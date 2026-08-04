import { useEffect, useRef, useState } from "react";

const EASE_OUT = (t: number) => 1 - Math.pow(1 - t, 3);

export function useCountUp(target: number, duration = 600): number {
  const [value, setValue] = useState(0);
  const prevTarget = useRef(0);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const from = prevTarget.current;
    const to = target;
    prevTarget.current = target;

    if (prefersReducedMotion || from === to) {
      setValue(to);
      return;
    }

    const start = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setValue(Math.round(from + (to - from) * EASE_OUT(progress)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}
