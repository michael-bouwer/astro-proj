import { Button, Heading, Text } from "@chakra-ui/react";
import type { Workspace } from "../../api/types";
import styles from "./WorkspaceHeader.module.scss";

export function WorkspaceHeader({
  workspace,
  onOpenHistory,
  onSaveVersion,
  saveDisabled,
}: {
  workspace: Workspace;
  onOpenHistory: () => void;
  onSaveVersion: () => void;
  saveDisabled: boolean;
}) {
  return (
    <div className={styles.header}>
      <div className={styles.titleGroup}>
        <Heading size="md">{workspace.name}</Heading>
        <Text className={styles.path}>{workspace.source_path}</Text>
      </div>
      <div className={styles.actions}>
        <Button variant="outline" onClick={onOpenHistory}>
          History
        </Button>
        <Button colorPalette="brand" onClick={onSaveVersion} disabled={saveDisabled}>
          Save Version
        </Button>
      </div>
    </div>
  );
}
