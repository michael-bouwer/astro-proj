import { useState } from "react";
import { Button, Dialog, Input, Portal, Text } from "@chakra-ui/react";
import { ApiError, createWorkspace } from "../../api/client";
import type { Workspace } from "../../api/types";
import styles from "./CreateWorkspaceDialog.module.scss";

const isTauri = typeof window !== "undefined" && ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

async function pickFolderNative(): Promise<string | null> {
  const { open } = await import("@tauri-apps/plugin-dialog");
  const result = await open({ directory: true, multiple: false });
  return typeof result === "string" ? result : null;
}

export function CreateWorkspaceDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (workspace: Workspace) => void;
}) {
  const [name, setName] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setName("");
    setSourcePath("");
    setError("");
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handlePickFolder = async () => {
    try {
      const picked = await pickFolderNative();
      if (picked) setSourcePath(picked);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open folder picker");
    }
  };

  const handleCreate = async () => {
    if (!name.trim() || !sourcePath.trim()) {
      setError("Name and folder are both required.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const workspace = await createWorkspace(name.trim(), sourcePath.trim());
      reset();
      onCreated(workspace);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create workspace");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(details) => !details.open && handleClose()}>
      <Portal>
        <Dialog.Backdrop className={styles.backdrop} />
        <Dialog.Positioner className={styles.positioner}>
          <Dialog.Content className={styles.content}>
            <Dialog.Title>New workspace</Dialog.Title>

            <div className={styles.field}>
              <Text className={styles.label}>Name</Text>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Orion nebula — session 3" />
            </div>

            <div className={styles.field}>
              <Text className={styles.label}>Frames folder</Text>
              <div className={styles.pathRow}>
                <Input
                  className={styles.pathInput}
                  value={sourcePath}
                  onChange={(e) => setSourcePath(e.target.value)}
                  placeholder={isTauri ? "Choose a folder..." : "C:\\path\\to\\dataset"}
                  readOnly={isTauri}
                />
                {isTauri && (
                  <Button variant="outline" onClick={handlePickFolder}>
                    Browse
                  </Button>
                )}
              </div>
              <Text className={styles.hint}>
                Must contain a lights/ subfolder (optionally darks/, flats/, biases/). Referenced in place -- nothing
                is copied.
              </Text>
            </div>

            {error && <Text className={styles.error}>{error}</Text>}

            <div className={styles.footer}>
              <Button variant="ghost" onClick={handleClose}>
                Cancel
              </Button>
              <Button colorPalette="brand" onClick={handleCreate} loading={submitting}>
                Create
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
