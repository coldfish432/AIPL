export type SaveJsonOptions = {
  suggestedName: string;
  description?: string;
};

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function saveJsonFile(data: unknown, options: SaveJsonOptions): Promise<void> {
  const text = JSON.stringify(data, null, 2);
  const nativeSave = (window as any).aipl?.saveJsonFile as
    | ((payload: { suggestedName?: string; data?: string }) => Promise<string | null>)
    | undefined;
  if (nativeSave) {
    const saved = await nativeSave({ suggestedName: options.suggestedName, data: text });
    if (!saved) return;
    return;
  }
  const picker = (window as any).showSaveFilePicker as
    | ((opts: Record<string, unknown>) => Promise<{ createWritable: () => Promise<{ write: (payload: string) => Promise<void>; close: () => Promise<void> }> }>)
    | undefined;

  if (picker) {
    try {
      const handle = await picker({
        suggestedName: options.suggestedName,
        types: [
          {
            description: options.description || "JSON",
            accept: { "application/json": [".json"] }
          }
        ]
      });
      const writable = await handle.createWritable();
      await writable.write(text);
      await writable.close();
      return;
    } catch (err) {
      if (isAbortError(err)) return;
      throw err;
    }
  }

  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = options.suggestedName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function pickWorkspaceDirectory(): Promise<string | null> {
  const nativePicker = (window as any).aipl?.pickWorkspaceDirectory as
    | (() => Promise<string | null>)
    | undefined;
  if (nativePicker) {
    try {
      const nativePath = await nativePicker();
      if (nativePath) {
        return nativePath;
      }
      return null;
    } catch {
      return null;
    }
  }

  const picker = (window as any).showDirectoryPicker as
    | (() => Promise<{ name?: string; getFileHandle?: unknown; } & { resolve?: () => Promise<string[]> }>)
    | undefined;
  if (picker) {
    try {
      const handle = await picker();
      const pathParts = await handle.resolve?.();
      if (pathParts && pathParts.length) {
        return pathParts.join("/");
      }
      return handle.name || null;
    } catch (err) {
      if (isAbortError(err)) return null;
      throw err;
    }
  }
  const manual = window.prompt("Workspace path");
  return manual ? manual.trim() : null;
}
