import { IconButton } from "@chakra-ui/react";
import { useThemeMode } from "../../theme/ThemeModeProvider";
import styles from "./ThemeToggle.module.scss";

function SunIcon() {
  return (
    <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
    </svg>
  );
}

export function ThemeToggle() {
  const { mode, toggleMode } = useThemeMode();

  return (
    <IconButton
      className={styles.toggle}
      aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggleMode}
      variant="ghost"
      colorPalette="brand"
      size="sm"
    >
      {mode === "dark" ? <SunIcon /> : <MoonIcon />}
    </IconButton>
  );
}
