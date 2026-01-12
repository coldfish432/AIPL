import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("aipl", {
  saveJsonFile: (payload: { suggestedName?: string; data?: string }) => {
    return ipcRenderer.invoke("aipl-save-json", payload);
  },
  pickWorkspaceDirectory: () => {
    return ipcRenderer.invoke("aipl-pick-workspace");
  }
});

contextBridge.exposeInMainWorld("electronAPI", {
  pickWorkspace: () => {
    return ipcRenderer.invoke("aipl-pick-workspace");
  }
});
