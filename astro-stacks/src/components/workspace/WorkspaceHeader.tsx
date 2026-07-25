import { Button, Heading, IconButton, Text } from "@chakra-ui/react";
import type { Workspace } from "../../api/types";
import { CategoryEditor } from "./CategoryEditor";
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
  categorySuggestions,
  onOpenHistory,
  onOpenFrameQuality,
  onSaveVersion,
  saveDisabled,
  onEdit,
  onDelete,
  onToggleFavourite,
  onSetCategories,
}: {
  workspace: Workspace;
  categorySuggestions: string[];
  onOpenHistory: () => void;
  onOpenFrameQuality: () => void;
  onSaveVersion: () => void;
  saveDisabled: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onToggleFavourite: () => void;
  onSetCategories: (categories: string[]) => void;
}) {
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
          <CategoryEditor categories={workspace.categories} suggestions={categorySuggestions} onChange={onSetCategories} />
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
