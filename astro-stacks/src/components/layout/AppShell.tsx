import type { ReactNode } from "react";
import { Heading } from "@chakra-ui/react";
import { SystemStats } from "./SystemStats";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./AppShell.module.scss";

export function AppShell({
  children,
  onTitleClick,
  actions,
  tabBar,
}: {
  children: ReactNode;
  onTitleClick?: () => void;
  actions?: ReactNode;
  tabBar?: ReactNode;
}) {
  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <button className={styles.brandButton} onClick={onTitleClick} type="button">
          <Heading size="md">Astro Stacks</Heading>
        </button>
        <div className={styles.actions}>
          {actions}
          <SystemStats />
          <ThemeToggle />
        </div>
      </header>
      {tabBar}
      <main className={styles.content}>{children}</main>
    </div>
  );
}
