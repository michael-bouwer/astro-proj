import { useEffect, useState } from "react";
import { Button, Heading, IconButton, Spinner, Text } from "@chakra-ui/react";
import { ApiError, deleteWorkspace, listWorkspaces } from "../../api/client";
import type { Workspace } from "../../api/types";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import { ConfirmDialog } from "../common/ConfirmDialog";
import styles from "./WorkspaceList.module.scss";

function PencilIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      width={14}
      height={14}
    >
      <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      width={14}
      height={14}
    >
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6h16Z" />
    </svg>
  );
}

export function WorkspaceList({
  active,
  onOpenWorkspace,
  onWorkspaceDeleted,
  onWorkspaceRenamed,
}: {
  active: boolean;
  onOpenWorkspace: (workspace: Workspace) => void;
  onWorkspaceDeleted: (workspaceId: string) => void;
  onWorkspaceRenamed: (workspace: Workspace) => void;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(
    null,
  );
  const [deletingWorkspace, setDeletingWorkspace] = useState<Workspace | null>(
    null,
  );

  const refresh = () => {
    listWorkspaces()
      .then((res) => setWorkspaces(res.workspaces))
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Failed to load workspaces",
        ),
      );
  };

  // Since tabs keep this mounted permanently (rather than remounting on
  // navigation), refetch every time the user comes back to this tab so newly
  // created workspaces or freshly-stacked masters show up.
  useEffect(() => {
    if (active) refresh();
  }, [active]);

  const closeDialog = () => {
    setCreateOpen(false);
    setEditingWorkspace(null);
  };

  const handleDelete = async () => {
    if (!deletingWorkspace) return;
    await deleteWorkspace(deletingWorkspace.id);
    onWorkspaceDeleted(deletingWorkspace.id);
    setDeletingWorkspace(null);
    refresh();
  };

  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        <div>
          <Heading size="lg">Workspaces</Heading>
          <Text className={styles.subtitle}>
            Each workspace points at a frames folder on disk and keeps its own
            stacked versions.
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
          <Text>
            No workspaces yet. Create one to point at a lights/ folder and start
            stacking.
          </Text>
        </div>
      )}

      {workspaces !== null && workspaces.length > 0 && (
        <div className={styles.grid}>
          {workspaces.map((ws) => (
            <div
              key={ws.id}
              className={styles.card}
              role="button"
              tabIndex={0}
              onClick={() => onOpenWorkspace(ws)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onOpenWorkspace(ws);
              }}
            >
              <span
                className={styles.badge}
                style={{
                  background: ws.has_master
                    ? "var(--chakra-colors-brand-subtle)"
                    : "var(--chakra-colors-yellow-800)",
                  color: ws.has_master
                    ? "var(--chakra-colors-brand-fg)"
                    : "var(--chakra-colors-yellow-100)",
                }}
              >
                {ws.has_master ? "Stacked" : "In Progress"}
              </span>

              <div className={styles.cardActions}>
                <IconButton
                  size="2xs"
                  variant="ghost"
                  aria-label={`Edit ${ws.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingWorkspace(ws);
                  }}
                >
                  <PencilIcon />
                </IconButton>
                <IconButton
                  size="2xs"
                  variant="ghost"
                  colorPalette="red"
                  aria-label={`Delete ${ws.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeletingWorkspace(ws);
                  }}
                >
                  <TrashIcon />
                </IconButton>
              </div>
              <Heading size="md">{ws.name}</Heading>
              <Text className={styles.path}>{ws.source_path}</Text>
              <div className={styles.stats}>
                <span>{ws.frame_counts.lights} lights</span>
                <span>{ws.frame_counts.darks} darks</span>
                <span>{ws.frame_counts.flats} flats</span>
                <span>{ws.frame_counts.biases} biases</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <CreateWorkspaceDialog
        open={createOpen || editingWorkspace !== null}
        onClose={closeDialog}
        editingWorkspace={editingWorkspace}
        onCreated={(ws) => {
          closeDialog();
          onOpenWorkspace(ws);
        }}
        onSaved={(ws) => {
          closeDialog();
          onWorkspaceRenamed(ws);
          refresh();
        }}
      />

      <ConfirmDialog
        open={deletingWorkspace !== null}
        title="Delete workspace?"
        message={
          deletingWorkspace
            ? `This removes "${deletingWorkspace.name}" and all its saved versions. The source frames folder itself is not touched.`
            : ""
        }
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeletingWorkspace(null)}
      />
    </div>
  );
}
