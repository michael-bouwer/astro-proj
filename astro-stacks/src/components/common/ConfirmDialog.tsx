import { useState } from "react";
import { Button, Dialog, Portal, Text } from "@chakra-ui/react";
import styles from "./ConfirmDialog.module.scss";

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(details) => !details.open && onCancel()}>
      <Portal>
        <Dialog.Backdrop className={styles.backdrop} />
        <Dialog.Positioner className={styles.positioner}>
          <Dialog.Content className={styles.content}>
            <Dialog.Title>{title}</Dialog.Title>
            <Text className={styles.message}>{message}</Text>
            <div className={styles.footer}>
              <Button variant="ghost" onClick={onCancel}>
                Cancel
              </Button>
              <Button colorPalette={danger ? "red" : "brand"} onClick={handleConfirm} loading={submitting}>
                {confirmLabel}
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
