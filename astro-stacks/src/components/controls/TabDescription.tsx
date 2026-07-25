import { Text } from "@chakra-ui/react";
import styles from "./TabDescription.module.scss";

// A one-or-two-sentence orientation blurb at the top of each ControlsPanel
// tab -- what this tab's settings do and, importantly, whether/when they
// touch the actual pipeline run vs. only the display-time preview/export.
export function TabDescription({ children }: { children: string }) {
  return <Text className={styles.description}>{children}</Text>;
}
