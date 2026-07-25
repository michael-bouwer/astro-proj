import { useRef, useState } from "react";
import { Input } from "@chakra-ui/react";
import styles from "./CategoryEditor.module.scss";

let datalistIdCounter = 0;

// Shared by the workspace list cards and the open-workspace header -- a row
// of removable category chips plus an add control. Suggestions come from
// GET /categories (every category currently in use, most-recently-used
// first, per pipeline/workspace.py's list_categories) and are offered via a
// native <datalist> on the add input, so typing shows the browser's own
// autocomplete dropdown without a custom combobox implementation. Free text
// is still accepted -- the datalist only suggests, it doesn't restrict.
export function CategoryEditor({
  categories,
  suggestions,
  onChange,
}: {
  categories: string[];
  suggestions: string[];
  onChange: (categories: string[]) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const datalistId = useRef(`category-suggestions-${++datalistIdCounter}`).current;

  // Already-added categories don't need to be suggested again.
  const availableSuggestions = suggestions.filter((s) => !categories.includes(s));

  const commitDraft = () => {
    const name = draft.trim();
    setDraft("");
    if (name && !categories.includes(name)) onChange([...categories, name]);
  };

  const removeCategory = (name: string) => {
    onChange(categories.filter((c) => c !== name));
  };

  return (
    <div className={styles.row}>
      {categories.map((name) => (
        <span key={name} className={styles.chip}>
          {name}
          <button
            type="button"
            className={styles.chipRemove}
            aria-label={`Remove category ${name}`}
            onClick={(e) => {
              e.stopPropagation();
              removeCategory(name);
            }}
          >
            ×
          </button>
        </span>
      ))}

      {adding ? (
        <>
          <Input
            size="xs"
            className={styles.input}
            autoFocus
            list={datalistId}
            value={draft}
            placeholder="Category..."
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => {
              commitDraft();
              setAdding(false);
            }}
            onKeyDown={(e) => {
              // Enter adds and keeps the input open, for adding several in a
              // row -- only Escape/blur close it.
              if (e.key === "Enter") {
                e.preventDefault();
                commitDraft();
              }
              if (e.key === "Escape") {
                setDraft("");
                setAdding(false);
              }
            }}
          />
          <datalist id={datalistId}>
            {availableSuggestions.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </>
      ) : (
        <button
          type="button"
          className={styles.addTag}
          onClick={(e) => {
            e.stopPropagation();
            setAdding(true);
          }}
        >
          {categories.length === 0 ? "+ Add category" : "+"}
        </button>
      )}
    </div>
  );
}
