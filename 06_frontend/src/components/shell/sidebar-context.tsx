"use client";

import * as React from "react";

type SidebarContextValue = {
  open: boolean;
  toggle: () => void;
  close: () => void;
};

export const SidebarContext = React.createContext<SidebarContextValue>({
  open: false,
  toggle: () => {},
  close: () => {},
});

export function useSidebar() {
  return React.useContext(SidebarContext);
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const toggle = React.useCallback(() => setOpen((v) => !v), []);
  const close = React.useCallback(() => setOpen(false), []);
  return (
    <SidebarContext.Provider value={{ open, toggle, close }}>
      {children}
    </SidebarContext.Provider>
  );
}
