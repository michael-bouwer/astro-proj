/**
 * Single source of truth for the app's accent color.
 *
 * Edit `brandScale` below to reskin the whole app -- every Chakra component
 * that uses `colorPalette="brand"` (buttons, checkboxes, tabs, focus rings, ...)
 * and every custom panel in components/**\/*.module.scss reads its colors from
 * the CSS variables Chakra generates from these tokens (--chakra-colors-brand-*),
 * so nothing else needs to change. Everything else (neutral backgrounds, text,
 * borders, status colors) comes from Chakra's built-in gray/red/green/orange
 * scales, which already have good light/dark semantics.
 */
export const brandScale = {
  50: { value: "#eef2ff" },
  100: { value: "#e0e7ff" },
  200: { value: "#c7d2fe" },
  300: { value: "#a5b4fc" },
  400: { value: "#818cf8" },
  500: { value: "#6366f1" },
  600: { value: "#4f46e5" },
  700: { value: "#4338ca" },
  800: { value: "#3730a3" },
  900: { value: "#312e81" },
  950: { value: "#1e1b4b" },
};
