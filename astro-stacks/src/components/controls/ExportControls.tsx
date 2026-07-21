import { useState } from "react";
import { Button, Checkbox, Input, Text } from "@chakra-ui/react";
import { ApiError, exportWorkspace } from "../../api/client";
import type { ExportFormat, MasterDimensions, RunParams, RunResult, StretchParams, TransformParams, Workspace } from "../../api/types";
import { simplifyRatio } from "../../utils/imageGeometry";
import { buildDefaultExportFilename } from "../../utils/exportFilename";
import styles from "./ExportControls.module.scss";

const isTauri = typeof window !== "undefined" && ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

const FORMATS: { value: ExportFormat; label: string; extension: string }[] = [
  { value: "tiff", label: "TIFF (16-bit)", extension: "tiff" },
  { value: "png", label: "PNG (16-bit)", extension: "png" },
  { value: "jpeg", label: "JPEG (8-bit)", extension: "jpg" },
];

async function pickSaveDestination(defaultPath: string, extension: string): Promise<string | null> {
  const { save } = await import("@tauri-apps/plugin-dialog");
  const result = await save({
    defaultPath,
    filters: [{ name: extension.toUpperCase(), extensions: [extension] }],
  });
  return typeof result === "string" ? result : null;
}

export function ExportControls({
  workspaceId,
  workspace,
  masterLoaded,
  masterDimensions,
  stretchParams,
  transformParams,
  runParams,
  runResult,
}: {
  workspaceId: string;
  workspace: Workspace;
  masterLoaded: boolean;
  masterDimensions: MasterDimensions | null;
  stretchParams: StretchParams;
  transformParams: TransformParams;
  runParams: RunParams | null;
  runResult: RunResult | null;
}) {
  const [format, setFormat] = useState<ExportFormat>("tiff");
  const [fixHalos, setFixHalos] = useState(true);
  const [filename, setFilename] = useState(() => buildDefaultExportFilename({ workspace, runParams, runResult }));
  const [destinationFolder, setDestinationFolder] = useState("");
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [exportedPath, setExportedPath] = useState<string | null>(null);

  const extension = FORMATS.find((f) => f.value === format)!.extension;
  const baseName = filename.trim() || "export";

  let sizeLabel = "Unknown";
  if (masterDimensions) {
    const crop = transformParams.crop ?? { x: 0, y: 0, width: 1, height: 1 };
    const width = Math.round(crop.width * masterDimensions.width);
    const height = Math.round(crop.height * masterDimensions.height);
    sizeLabel = `${width} × ${height} px · ${simplifyRatio(width, height)}`;
  }

  const handleSuggestName = () => {
    setFilename(buildDefaultExportFilename({ workspace, runParams, runResult }));
  };

  const handleExport = async () => {
    setError("");
    setExportedPath(null);

    let destinationPath: string | null = null;
    if (isTauri) {
      try {
        destinationPath = await pickSaveDestination(`${baseName}.${extension}`, extension);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to open the save dialog");
        return;
      }
      if (!destinationPath) return; // user cancelled the dialog
    } else {
      if (!destinationFolder.trim()) {
        setError("Enter a destination folder.");
        return;
      }
      destinationPath = `${destinationFolder.trim().replace(/[\\/]+$/, "")}/${baseName}.${extension}`;
    }

    setExporting(true);
    try {
      const result = await exportWorkspace(workspaceId, {
        ...stretchParams,
        fix_halos: fixHalos,
        rotation: transformParams.rotationDeg,
        ...(transformParams.crop
          ? {
              crop_x: transformParams.crop.x,
              crop_y: transformParams.crop.y,
              crop_width: transformParams.crop.width,
              crop_height: transformParams.crop.height,
            }
          : {}),
        format,
        destination_path: destinationPath,
      });
      setExportedPath(result.path);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to export image");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className={styles.section}>
      <div className={styles.field}>
        <Text className={styles.label}>Export size</Text>
        <Text className={styles.infoText}>{sizeLabel}</Text>
        <Text className={styles.hint}>
          Matches the preview -- current stretch, crop, and rotation, exactly as shown.
        </Text>
      </div>

      <div className={styles.field}>
        <Text className={styles.label}>Format</Text>
        <div className={styles.segmented}>
          {FORMATS.map((f) => (
            <Button
              key={f.value}
              size="sm"
              variant={format === f.value ? "solid" : "outline"}
              colorPalette="brand"
              onClick={() => setFormat(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      <Checkbox.Root checked={fixHalos} onCheckedChange={(details) => setFixHalos(details.checked === true)}>
        <Checkbox.HiddenInput />
        <Checkbox.Control />
        <Checkbox.Label>Fix star halos</Checkbox.Label>
      </Checkbox.Root>

      <div className={styles.field}>
        <Text className={styles.label}>File name</Text>
        <div className={styles.pathRow}>
          <Input className={styles.pathInput} value={filename} onChange={(e) => setFilename(e.target.value)} />
          <Text className={styles.extension}>.{extension}</Text>
        </div>
        <Button variant="ghost" size="xs" alignSelf="flex-start" onClick={handleSuggestName}>
          Suggest name
        </Button>
      </div>

      {!isTauri && (
        <div className={styles.field}>
          <Text className={styles.label}>Destination folder</Text>
          <Input
            value={destinationFolder}
            onChange={(e) => setDestinationFolder(e.target.value)}
            placeholder="C:\path\to\folder"
          />
        </div>
      )}

      {error && <Text className={styles.error}>{error}</Text>}
      {exportedPath && <Text className={styles.success}>Exported to {exportedPath}</Text>}

      <Button colorPalette="brand" onClick={handleExport} loading={exporting} disabled={!masterLoaded}>
        {isTauri ? "Choose destination & export..." : "Export"}
      </Button>
    </div>
  );
}
