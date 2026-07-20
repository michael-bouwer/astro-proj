import { useState } from "react";
import { AppShell } from "./components/layout/AppShell";
import { TabBar, type OpenTab } from "./components/layout/TabBar";
import { WorkspaceList } from "./components/workspace/WorkspaceList";
import { WorkspaceDetail } from "./components/workspace/WorkspaceDetail";
import type { Workspace } from "./api/types";
import styles from "./App.module.scss";

function App() {
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null); // null = "Workspaces" home tab

  const openWorkspace = (workspace: Workspace) => {
    setOpenTabs((prev) =>
      prev.some((tab) => tab.workspaceId === workspace.id)
        ? prev
        : [...prev, { workspaceId: workspace.id, name: workspace.name }],
    );
    setActiveTabId(workspace.id);
  };

  const closeTab = (workspaceId: string) => {
    setOpenTabs((prev) => {
      const closingIndex = prev.findIndex(
        (tab) => tab.workspaceId === workspaceId,
      );
      const next = prev.filter((tab) => tab.workspaceId !== workspaceId);

      if (activeTabId === workspaceId) {
        const fallback = next[closingIndex - 1] ?? next[closingIndex] ?? null;
        setActiveTabId(fallback ? fallback.workspaceId : null);
      }

      return next;
    });
  };

  const renameTab = (workspace: Workspace) => {
    setOpenTabs((prev) =>
      prev.map((tab) =>
        tab.workspaceId === workspace.id
          ? { ...tab, name: workspace.name }
          : tab,
      ),
    );
  };

  return (
    <AppShell
      onTitleClick={() => setActiveTabId(null)}
      tabBar={
        <TabBar
          tabs={openTabs}
          activeTabId={activeTabId}
          isHomeActive={activeTabId === null}
          onSelectHome={() => setActiveTabId(null)}
          onSelect={setActiveTabId}
          onClose={closeTab}
        />
      }
    >
      <div className={activeTabId === null ? styles.panel : styles.panelHidden}>
        <WorkspaceList
          active={activeTabId === null}
          onOpenWorkspace={openWorkspace}
          onWorkspaceDeleted={closeTab}
          onWorkspaceRenamed={renameTab}
        />
      </div>

      {openTabs.map((tab) => (
        <div
          key={tab.workspaceId}
          className={
            activeTabId === tab.workspaceId ? styles.panel : styles.panelHidden
          }
        >
          <WorkspaceDetail
            workspaceId={tab.workspaceId}
            onDeleted={() => closeTab(tab.workspaceId)}
            onRenamed={renameTab}
          />
        </div>
      ))}
    </AppShell>
  );
}

export default App;
