import { useState } from "react";
import { Button, Heading, IconButton, Input, Text } from "@chakra-ui/react";
import type { Workspace } from "../../api/types";
import styles from "./WorkspaceHeader.module.scss";

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={2} width={16} height={16}>
      <path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14l-5-4.87 6.91-1.01L12 2Z" />
    </svg>
  );
}

export function WorkspaceHeader({
  workspace,
  onOpenHistory,
  onOpenFrameQuality,
  onSaveVersion,
  saveDisabled,
  onEdit,
  onDelete,
  onToggleFavourite,
  onSetCategory,
}: {
  workspace: Workspace;
  onOpenHistory: () => void;
  onOpenFrameQuality: () => void;
  onSaveVersion: () => void;
  saveDisabled: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onToggleFavourite: () => void;
  onSetCategory: (category: string) => void;
}) {
  // Local editing state (draft text + edit-mode toggle) so this mirrors the
  // same inline-edit UX as the workspace list's category tag -- favouriting/
  // categorizing shouldn't require leaving the workspace to go back to the list.
  const [editingCategory, setEditingCategory] = useState(false);
  const [categoryDraft, setCategoryDraft] = useState(workspace.category ?? "");

  const startEditingCategory = () => {
    setCategoryDraft(workspace.category ?? "");
    setEditingCategory(true);
  };

  const commitCategory = () => {
    setEditingCategory(false);
    const trimmed = categoryDraft.trim();
    if (trimmed !== (workspace.category ?? "")) onSetCategory(trimmed);
  };

  return (
    <div className={styles.header}>
      <div className={styles.titleGroup}>
        <div className={styles.titleRow}>
          <IconButton
            size="xs"
            variant="ghost"
            colorPalette={workspace.favourite ? "yellow" : "gray"}
            aria-label={workspace.favourite ? "Unfavourite workspace" : "Favourite workspace"}
            onClick={onToggleFavourite}
          >
            <StarIcon filled={workspace.favourite} />
          </IconButton>
          <Heading size="md">{workspace.name}</Heading>
          {editingCategory ? (
            <Input
              size="xs"
              className={styles.categoryInput}
              autoFocus
              value={categoryDraft}
              placeholder="e.g. Orion Nebula"
              onChange={(e) => setCategoryDraft(e.target.value)}
              onBlur={commitCategory}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                if (e.key === "Escape") setEditingCategory(false);
              }}
            />
          ) : (
            <button type="button" className={styles.categoryTag} onClick={startEditingCategory}>
              {workspace.category ?? "+ Add category"}
            </button>
          )}
        </div>
        <Text className={styles.path}>{workspace.source_path}</Text>
      </div>
      <div className={styles.actions}>
        <Button variant="ghost" onClick={onEdit}>
          Edit
        </Button>
        <Button variant="ghost" colorPalette="red" onClick={onDelete}>
          Delete
        </Button>
        <Button variant="outline" onClick={onOpenFrameQuality}>
          Frame Quality
        </Button>
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
