import { useEffect, useState } from "react";
import { Button, Heading, Spinner, Text } from "@chakra-ui/react";
import { ApiError, listWorkspaces } from "../../api/client";
import type { Workspace } from "../../api/types";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import styles from "./WorkspaceList.module.scss";

export function WorkspaceList({
  active,
  onOpenWorkspace,
}: {
  active: boolean;
  onOpenWorkspace: (workspace: Workspace) => void;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const refresh = () => {
    listWorkspaces()
      .then((res) => setWorkspaces(res.workspaces))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load workspaces"));
  };

  // Since tabs keep this mounted permanently (rather than remounting on
  // navigation), refetch every time the user comes back to this tab so newly
  // created workspaces or freshly-stacked masters show up.
  useEffect(() => {
    if (active) refresh();
  }, [active]);

  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        <div>
          <Heading size="lg">Workspaces</Heading>
          <Text className={styles.subtitle}>
            Each workspace points at a frames folder on disk and keeps its own stacked versions.
          </Text>
        </div>
        <Button colorPalette="brand" onClick={() => setCreateOpen(true)}>
          New Workspace
        </Button>
      </div>

      {error && <Text className={styles.error}>{error}</Text>}
      {workspaces === null && !error && <Spinner />}

      {workspaces !== null && workspaces.length === 0 && (
        <div className={styles.empty}>
          <Text>No workspaces yet. Create one to point at a lights/ folder and start stacking.</Text>
        </div>
      )}

      {workspaces !== null && workspaces.length > 0 && (
        <div className={styles.grid}>
          {workspaces.map((ws) => (
            <button key={ws.id} className={styles.card} onClick={() => onOpenWorkspace(ws)} type="button">
              {ws.has_master && <span className={styles.badge}>Stacked</span>}
              <Heading size="md">{ws.name}</Heading>
              <Text className={styles.path}>{ws.source_path}</Text>
              <div className={styles.stats}>
                <span>{ws.frame_counts.lights} lights</span>
                <span>{ws.frame_counts.darks} darks</span>
                <span>{ws.frame_counts.flats} flats</span>
                <span>{ws.frame_counts.biases} biases</span>
              </div>
            </button>
          ))}
        </div>
      )}

      <CreateWorkspaceDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(ws) => {
          setCreateOpen(false);
          onOpenWorkspace(ws);
        }}
      />
    </div>
  );
}
