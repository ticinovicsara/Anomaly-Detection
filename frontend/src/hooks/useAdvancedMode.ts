import { useEffect, useState } from "react";

const STORAGE_KEY = "advanced_mode";
const EVENT = "advanced-mode-changed";

/** Progressive-disclosure toggle: off by default, persisted in localStorage,
 * broadcast via a custom event so every mounted consumer (Subject detail,
 * Upload, Models, ...) re-renders immediately when it changes, with no
 * route reload and no prop drilling from Settings. */
export function useAdvancedMode() {
  const [enabled, setEnabled] = useState<boolean>(() => localStorage.getItem(STORAGE_KEY) === "true");

  useEffect(() => {
    const listener = () => setEnabled(localStorage.getItem(STORAGE_KEY) === "true");
    window.addEventListener(EVENT, listener);
    return () => window.removeEventListener(EVENT, listener);
  }, []);

  const toggle = () => {
    const next = !enabled;
    localStorage.setItem(STORAGE_KEY, String(next));
    setEnabled(next);
    window.dispatchEvent(new Event(EVENT));
  };

  return { enabled, toggle };
}
