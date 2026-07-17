/** Theme switching: stamps data-theme on <html>, persists the choice.
 * Without a stored choice the OS preference applies via CSS alone. */

import { useCallback, useSyncExternalStore } from "react";

export type Theme = "dark" | "light";
const STORAGE_KEY = "collector.theme";

function readStored(): Theme | null {
  const value = localStorage.getItem(STORAGE_KEY);
  return value === "dark" || value === "light" ? value : null;
}

export function currentTheme(): Theme {
  const stored = readStored();
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyStoredTheme(): void {
  const stored = readStored();
  if (stored) document.documentElement.dataset.theme = stored;
}

const listeners = new Set<() => void>();

function setTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  document.documentElement.dataset.theme = theme;
  listeners.forEach((notify) => notify());
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const theme = useSyncExternalStore(
    (notify) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    currentTheme,
  );
  const toggle = useCallback(() => {
    setTheme(currentTheme() === "dark" ? "light" : "dark");
  }, []);
  return { theme, toggle };
}
