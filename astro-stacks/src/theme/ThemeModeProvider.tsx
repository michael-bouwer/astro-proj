import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemeMode = "dark" | "light";

interface ThemeModeContextValue {
  mode: ThemeMode;
  toggleMode: () => void;
}

const STORAGE_KEY = "astro-stacks-theme-mode";
const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);

function readStoredMode(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  return window.localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
}

// Toggles a `dark`/`light` class on <html> -- this is the exact selector Chakra's
// built-in _dark/_light semantic token conditions key off (see
// node_modules/@chakra-ui/react preset-base), so no custom condition config is
// needed for Chakra components or semantic tokens to respond to this.
export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(readStoredMode);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove(mode === "dark" ? "light" : "dark");
    root.classList.add(mode);
    window.localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const toggleMode = () => setMode((prev) => (prev === "dark" ? "light" : "dark"));

  return <ThemeModeContext.Provider value={{ mode, toggleMode }}>{children}</ThemeModeContext.Provider>;
}

export function useThemeMode(): ThemeModeContextValue {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) throw new Error("useThemeMode must be used within ThemeModeProvider");
  return ctx;
}
