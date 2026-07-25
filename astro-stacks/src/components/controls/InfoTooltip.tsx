import { Portal, Tooltip } from "@chakra-ui/react";
import styles from "./InfoTooltip.module.scss";

// A small hover/focus target that explains what changing a control's value
// does -- kept as its own component since it's reused next to every field
// label across the Stacking/Stretch/Effects/Crop/Export tabs.
export function InfoTooltip({ label }: { label: string }) {
  return (
    <Tooltip.Root openDelay={200} closeDelay={100} positioning={{ placement: "top" }}>
      <Tooltip.Trigger asChild>
        <span className={styles.trigger} tabIndex={0} role="button" aria-label={`About: ${label}`}>
          ?
        </span>
      </Tooltip.Trigger>
      <Portal>
        <Tooltip.Positioner>
          <Tooltip.Content className={styles.content}>{label}</Tooltip.Content>
        </Tooltip.Positioner>
      </Portal>
    </Tooltip.Root>
  );
}
