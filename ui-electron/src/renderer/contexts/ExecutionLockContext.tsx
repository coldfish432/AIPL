import React, { createContext, useContext } from "react";
import { useEnhancedLock } from "@/hooks/useEnhancedLock";
import type { UseEnhancedLockReturn } from "@/hooks/useEnhancedLock";

const ExecutionLockContext = createContext<UseEnhancedLockReturn | null>(null);

interface ExecutionLockProviderProps {
  children: React.ReactNode;
}

export function ExecutionLockProvider({ children }: ExecutionLockProviderProps) {
  const lockState = useEnhancedLock();
  return (
    <ExecutionLockContext.Provider value={lockState}>
      {children}
    </ExecutionLockContext.Provider>
  );
}

export function useExecutionLock(): UseEnhancedLockReturn {
  const ctx = useContext(ExecutionLockContext);
  if (!ctx) {
    throw new Error("useExecutionLock must be used within ExecutionLockProvider");
  }
  return ctx;
}
