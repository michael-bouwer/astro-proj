import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Heading, IconButton, Input, NativeSelect, Spinner, Text } from "@chakra-ui/react";
import {
  ApiError,
  deleteWorkspace,
  getCategories,
  listWorkspaces,
  reorderWorkspaces,
  setWorkspaceCategories,
  setWorkspaceFavourite,
} from "../../api/client";
import type { Workspace } from "../../api/types";
import { usePipelineJobs } from "../../state/PipelineJobsContext";
import { CategoryEditor } from "./CategoryEditor";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import { ConfirmDialog } from "../common/ConfirmDialog";
import styles from "./WorkspaceList.module.scss";

const PAGE_SIZE = 20;
// A card only starts "dragging" once the pointer has moved this many pixels
// from where it went down -- otherwise a plain click (to open the workspace)
// would register as a zero-distance drag.
const DRAG_THRESHOLD_PX = 6;

type SortMode = "none" | "category" | "created" | "modified";
type SortDirection = "asc" | "desc";

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "none", label: "No sort (drag to reorder)" },
  { value: "category", label: "Category" },
  { value: "created", label: "Date created" },
  { value: "modified", label: "Date modified" },
];

// The direction a freshly-selected sort mode starts in -- matches what felt
// like the "natural" default before asc/desc existed (categories A-Z, dates
// newest first), so picking a mode from the dropdown doesn't change behavior
// by itself; only the toggle button does.
const DEFAULT_DIRECTION: Record<SortMode, SortDirection> = {
  none: "asc",
  category: "asc",
  created: "desc",
  modified: "desc",
};

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={14} height={14}>
      <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={14} height={14}>
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6h16Z" />
    </svg>
  );
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={2} width={14} height={14}>
      <path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14l-5-4.87 6.91-1.01L12 2Z" />
    </svg>
  );
}

function SortDirectionIcon({ direction }: { direction: SortDirection }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} width={14} height={14}>
      {direction === "asc" ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M5 12l7 7 7-7" />}
    </svg>
  );
}

// Each case returns its own natural ascending order (category A-Z, dates
// oldest-first, manual order as-dragged) -- sortDirection flips the sign
// uniformly afterward, so this only needs to express "ascending" once per key.
function compareBySortMode(a: Workspace, b: Workspace, sortMode: SortMode): number {
  switch (sortMode) {
    case "category":
      // Multiple categories are allowed -- the first one (the primary tag,
      // in whatever order they were added) organizes the sort.
      return (a.categories[0] ?? "").localeCompare(b.categories[0] ?? "") || a.name.localeCompare(b.name);
    case "created":
      return a.created_at.localeCompare(b.created_at);
    case "modified":
      return a.updated_at.localeCompare(b.updated_at);
    case "none":
    default:
      return a.sort_order - b.sort_order || a.created_at.localeCompare(b.created_at);
  }
}

function moveBefore(list: Workspace[], draggedId: string, targetId: string): Workspace[] {
  const fromIndex = list.findIndex((w) => w.id === draggedId);
  const toIndex = list.findIndex((w) => w.id === targetId);
  if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) return list;
  const next = [...list];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(
    next.findIndex((w) => w.id === targetId),
    0,
    moved,
  );
  return next;
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
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);
  const [deletingWorkspace, setDeletingWorkspace] = useState<Workspace | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("none");
  const [sortDirection, setSortDirection] = useState<SortDirection>(DEFAULT_DIRECTION.none);
  const [page, setPage] = useState(1);

  const [categorySuggestions, setCategorySuggestions] = useState<string[]>([]);

  // Drag-to-reorder ("No sort" only) -- see handleCardPointerDown. Deliberately
  // pointer-events-based rather than the native HTML5 Drag and Drop API:
  // Tauri's webview intercepts OS-level drag gestures for its own file-drop
  // handling, which stops dragstart/dragover/drop from firing reliably for
  // in-page elements. Pointer events aren't part of that interception, so
  // this works the same in the Tauri window and in a plain dev browser.
  const [draggingWorkspaceId, setDraggingWorkspaceId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const suppressNextClickRef = useRef(false);

  const { activeWorkspaceId } = usePipelineJobs();

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

  useEffect(() => {
    if (!active) return;
    getCategories()
      .then((res) => setCategorySuggestions(res.categories))
      .catch(() => {
        // best-effort suggestions -- a failed fetch just means an empty list
      });
  }, [active]);

  // A new search/sort selection can shrink the result set out from under the
  // page you were on -- reset to page 1 rather than showing an empty page.
  useEffect(() => {
    setPage(1);
  }, [searchQuery, sortMode, sortDirection]);

  const filtered = useMemo(() => {
    if (!workspaces) return [];
    const query = searchQuery.trim().toLowerCase();
    if (!query) return workspaces;
    return workspaces.filter(
      (ws) =>
        ws.name.toLowerCase().includes(query) ||
        ws.categories.some((c) => c.toLowerCase().includes(query)) ||
        ws.source_path.toLowerCase().includes(query),
    );
  }, [workspaces, searchQuery]);

  const sorted = useMemo(() => {
    const directionMultiplier = sortDirection === "desc" ? -1 : 1;
    return [...filtered].sort((a, b) => {
      if (a.favourite !== b.favourite) return a.favourite ? -1 : 1;
      return compareBySortMode(a, b, sortMode) * directionMultiplier;
    });
  }, [filtered, sortMode, sortDirection]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const clampedPage = Math.min(page, pageCount);
  const pageItems = sorted.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);

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

  const handleToggleFavourite = async (ws: Workspace) => {
    const next = !ws.favourite;
    setWorkspaces((prev) => prev && prev.map((w) => (w.id === ws.id ? { ...w, favourite: next } : w)));
    try {
      await setWorkspaceFavourite(ws.id, next);
    } catch {
      refresh(); // best-effort optimistic update; fall back to server truth on failure
    }
  };

  const handleSetCategories = async (ws: Workspace, categories: string[]) => {
    setWorkspaces((prev) => prev && prev.map((w) => (w.id === ws.id ? { ...w, categories } : w)));
    try {
      await setWorkspaceCategories(ws.id, categories);
      getCategories()
        .then((res) => setCategorySuggestions(res.categories))
        .catch(() => {});
    } catch {
      refresh();
    }
  };

  const handleSortModeChange = (mode: SortMode) => {
    setSortMode(mode);
    setSortDirection(DEFAULT_DIRECTION[mode]);
  };

  const persistReorder = async (draggedId: string, targetId: string) => {
    if (!workspaces) return;
    const dragged = workspaces.find((w) => w.id === draggedId);
    const target = workspaces.find((w) => w.id === targetId);
    // Favourites always stay pinned above everything else -- dragging can't
    // cross that boundary, only reorder within the same group.
    if (!dragged || !target || dragged.favourite !== target.favourite) return;

    const reorderedVisible = moveBefore(sorted, draggedId, targetId);
    const orderById = new Map(reorderedVisible.map((w, index) => [w.id, index]));
    const reorderedAll = [...workspaces].sort((a, b) => (orderById.get(a.id) ?? 0) - (orderById.get(b.id) ?? 0));
    const orderedIds = reorderedAll.map((w) => w.id);

    setWorkspaces(reorderedAll.map((w, index) => ({ ...w, sort_order: index })));
    try {
      await reorderWorkspaces(orderedIds);
    } catch {
      refresh();
    }
  };

  // Starts tracking a potential drag from a pointerdown on a card. Listens on
  // `window` (not the card itself) for move/up so the drag keeps tracking
  // even once the pointer leaves the card's own bounds -- necessary since
  // cards aren't relatively huge and a real drag gesture routinely overshoots
  // past a neighbor's edge.
  const handleCardPointerDown = (e: React.PointerEvent<HTMLDivElement>, ws: Workspace) => {
    // Cleared on every new pointerdown, not just when a click consumes it --
    // a completed drag that ends over a *different* card never fires a click
    // on the card it started from (real cross-element drags don't), so
    // without this reset the flag could stay stuck true and swallow some
    // later, unrelated click.
    suppressNextClickRef.current = false;
    if (sortMode !== "none" || e.button !== 0) return;
    // Ignore drags started on nested interactive controls (favourite/edit/
    // delete buttons, the category input) so those clicks aren't hijacked.
    if ((e.target as HTMLElement).closest("button, input, a, select")) return;

    const startX = e.clientX;
    const startY = e.clientY;
    let moved = false;
    let overId: string | null = null;

    const handleMove = (moveEvent: PointerEvent) => {
      if (!moved) {
        const dx = moveEvent.clientX - startX;
        const dy = moveEvent.clientY - startY;
        if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
        moved = true;
        setDraggingWorkspaceId(ws.id);
      }
      const el = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY);
      const cardEl = el instanceof Element ? el.closest<HTMLElement>("[data-workspace-id]") : null;
      overId = cardEl?.dataset.workspaceId ?? null;
      setDragOverId((current) => (current === overId ? current : overId));
    };

    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleUp);
      if (moved) {
        suppressNextClickRef.current = true; // a real drag happened -- don't also open the workspace
        if (overId && overId !== ws.id) persistReorder(ws.id, overId);
      }
      setDraggingWorkspaceId(null);
      setDragOverId(null);
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleUp);
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

      <div className={styles.controlsRow}>
        <Input
          className={styles.searchInput}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search workspaces..."
        />
        <NativeSelect.Root size="sm" className={styles.sortSelect}>
          <NativeSelect.Field value={sortMode} onChange={(e) => handleSortModeChange(e.target.value as SortMode)}>
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </NativeSelect.Field>
          <NativeSelect.Indicator />
        </NativeSelect.Root>
        <IconButton
          size="sm"
          variant="outline"
          aria-label={sortDirection === "asc" ? "Sort ascending (click for descending)" : "Sort descending (click for ascending)"}
          title={sortDirection === "asc" ? "Ascending" : "Descending"}
          disabled={sortMode === "none"}
          onClick={() => setSortDirection((d) => (d === "asc" ? "desc" : "asc"))}
        >
          <SortDirectionIcon direction={sortDirection} />
        </IconButton>
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

      {workspaces !== null && workspaces.length > 0 && sorted.length === 0 && (
        <div className={styles.empty}>
          <Text>No workspaces match "{searchQuery}".</Text>
        </div>
      )}

      {pageItems.length > 0 && (
        <div className={styles.grid}>
          {pageItems.map((ws) => (
            <div
              key={ws.id}
              data-workspace-id={ws.id}
              className={[
                styles.card,
                dragOverId === ws.id ? styles.cardDragOver : "",
                draggingWorkspaceId === ws.id ? styles.cardDragging : "",
                sortMode === "none" ? styles.cardDraggable : "",
              ]
                .filter(Boolean)
                .join(" ")}
              role="button"
              tabIndex={0}
              onClick={() => {
                if (suppressNextClickRef.current) {
                  suppressNextClickRef.current = false;
                  return;
                }
                onOpenWorkspace(ws);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onOpenWorkspace(ws);
              }}
              onPointerDown={(e) => handleCardPointerDown(e, ws)}
            >
              {activeWorkspaceId === ws.id ? (
                <span className={`${styles.badge} ${styles.badgeStacking}`}>
                  <Spinner size="xs" />
                  Stacking...
                </span>
              ) : (
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
                  {ws.has_master ? "Stacked" : "Not stacked"}
                </span>
              )}

              <div className={styles.cardActions}>
                <IconButton
                  size="2xs"
                  variant="ghost"
                  colorPalette={ws.favourite ? "yellow" : "gray"}
                  aria-label={ws.favourite ? `Unfavourite ${ws.name}` : `Favourite ${ws.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleToggleFavourite(ws);
                  }}
                >
                  <StarIcon filled={ws.favourite} />
                </IconButton>
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

              <CategoryEditor
                categories={ws.categories}
                suggestions={categorySuggestions}
                onChange={(categories) => handleSetCategories(ws, categories)}
              />

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

      {
        <div className={styles.pagination}>
          <Button size="sm" variant="outline" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={clampedPage <= 1}>
            Previous
          </Button>
          <Text className={styles.pageLabel}>
            Page {clampedPage} of {pageCount} -- {sorted.length} workspace{sorted.length === 1 ? "" : "s"}
          </Text>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            disabled={clampedPage >= pageCount}
          >
            Next
          </Button>
        </div>
      }

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
