import { Text } from "@chakra-ui/react";
import { InfoTooltip } from "./InfoTooltip";
import styles from "./FieldLabel.module.scss";

// Drop-in replacement for the bare `<Text className={styles.label}>` row
// used at the top of most control fields -- adds an optional info tooltip
// without every control file needing its own row/label styling for it.
export function FieldLabel({ label, tooltip }: { label: string; tooltip?: string }) {
  return (
    <div className={styles.row}>
      <Text className={styles.label}>{label}</Text>
      {tooltip && <InfoTooltip label={tooltip} />}
    </div>
  );
}
