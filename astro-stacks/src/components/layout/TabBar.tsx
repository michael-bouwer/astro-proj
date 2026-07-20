import { CloseButton } from "@chakra-ui/react";
import styles from "./TabBar.module.scss";

export type OpenTab = {
  workspaceId: string;
  name: string;
};

export function TabBar({
  tabs,
  activeTabId,
  isHomeActive,
  onSelectHome,
  onSelect,
  onClose,
}: {
  tabs: OpenTab[];
  activeTabId: string | null;
  isHomeActive: boolean;
  onSelectHome: () => void;
  onSelect: (workspaceId: string) => void;
  onClose: (workspaceId: string) => void;
}) {
  return (
    <nav className={styles.bar}>
      <button
        type="button"
        className={`${styles.tab} ${styles.homeTab} ${isHomeActive ? styles.tabActive : ""}`}
        onClick={onSelectHome}
      >
        Workspaces
      </button>

      {tabs.map((tab) => (
        <div key={tab.workspaceId} className={`${styles.tab} ${activeTabId === tab.workspaceId ? styles.tabActive : ""}`}>
          <button type="button" className={styles.tabLabel} onClick={() => onSelect(tab.workspaceId)} title={tab.name}>
            {tab.name}
          </button>
          <CloseButton
            size="2xs"
            className={styles.tabClose}
            aria-label={`Close ${tab.name}`}
            onClick={(e) => {
              e.stopPropagation();
              onClose(tab.workspaceId);
            }}
          />
        </div>
      ))}
    </nav>
  );
}
