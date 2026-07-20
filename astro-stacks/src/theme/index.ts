import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";
import { brandScale } from "./colors";

const customConfig = defineConfig({
  theme: {
    tokens: {
      colors: {
        brand: brandScale,
      },
    },
    semanticTokens: {
      colors: {
        // Matches the shape Chakra's built-in palettes (blue, red, ...) use, so
        // `colorPalette="brand"` works on any Chakra component exactly like a
        // stock palette would.
        brand: {
          contrast: { value: { _light: "white", _dark: "white" } },
          fg: { value: { _light: "{colors.brand.700}", _dark: "{colors.brand.300}" } },
          subtle: { value: { _light: "{colors.brand.100}", _dark: "{colors.brand.900}" } },
          muted: { value: { _light: "{colors.brand.200}", _dark: "{colors.brand.800}" } },
          emphasized: { value: { _light: "{colors.brand.300}", _dark: "{colors.brand.700}" } },
          solid: { value: { _light: "{colors.brand.600}", _dark: "{colors.brand.500}" } },
          focusRing: { value: { _light: "{colors.brand.500}", _dark: "{colors.brand.500}" } },
          border: { value: { _light: "{colors.brand.500}", _dark: "{colors.brand.400}" } },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, customConfig);
