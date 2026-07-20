import { useEffect, useState } from "react";
import { CloseButton, Drawer, Heading, Portal, Text } from "@chakra-ui/react";
import { ApiError, listVersions, versionImageUrl } from "../../api/client";
import type { Version } from "../../api/types";
import styles from "./VersionHistoryDrawer.module.scss";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString();
}

function summarizeParams(version: Version): string {
  const { params } = version;
  const parts = [`stretch: ${params.method}`];
  if (params.integration_method) {
    parts.push(params.integration_method === "sigma_clip" ? "sigma-clip" : "median");
  }
  if (typeof params.sigma === "number") parts.push(`σ=${params.sigma.toFixed(1)}`);
  if (params.apply_dark === false) parts.push("no dark");
  if (params.apply_flat === false) parts.push("no flat");
  return parts.join(" · ");
}

export function VersionHistoryDrawer({
  open,
  onClose,
  workspaceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
}) {
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    listVersions(workspaceId)
      .then((res) => setVersions(res.versions))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load versions"));
  }, [open, workspaceId]);

  return (
    <Drawer.Root open={open} onOpenChange={(details) => !details.open && onClose()}>
      <Portal>
        <Drawer.Backdrop />
        <Drawer.Positioner>
          <Drawer.Content className={styles.content}>
            <Drawer.Header className={styles.header}>
              <Heading size="md">Version history</Heading>
              <Drawer.CloseTrigger asChild>
                <CloseButton size="sm" />
              </Drawer.CloseTrigger>
            </Drawer.Header>
            <Drawer.Body className={styles.body}>
              {error && <Text className={styles.error}>{error}</Text>}
              {versions !== null && versions.length === 0 && (
                <Text className={styles.empty}>No versions saved yet.</Text>
              )}
              {versions?.map((version) => (
                <a
                  key={version.id}
                  className={styles.item}
                  href={versionImageUrl(workspaceId, version.id, "export")}
                  target="_blank"
                  rel="noreferrer"
                >
                  <img
                    className={styles.thumbnail}
                    src={versionImageUrl(workspaceId, version.id, "thumbnail")}
                    alt=""
                  />
                  <div className={styles.itemBody}>
                    <Text className={styles.itemNote}>{version.note || "(no note)"}</Text>
                    <Text className={styles.itemMeta}>{summarizeParams(version)}</Text>
                    <Text className={styles.itemMeta}>
                      {formatTimestamp(version.created_at)}
                      {version.stats.snr_db !== null ? ` · SNR ${version.stats.snr_db.toFixed(1)} dB` : ""}
                    </Text>
                  </div>
                </a>
              ))}
            </Drawer.Body>
          </Drawer.Content>
        </Drawer.Positioner>
      </Portal>
    </Drawer.Root>
  );
}
