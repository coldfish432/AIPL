import React, { useEffect, useRef, useState } from "react";

interface WorkspaceSelectorProps {
  current: string;
  label: string;
  history: string[];
  onSelect: (value: string) => void;
  onBrowse: () => Promise<void>;
}

export default function WorkspaceSelector({ current, label, history, onSelect, onBrowse }: WorkspaceSelectorProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  const handleSelect = (value: string) => {
    onSelect(value);
    setOpen(false);
  };

  const displayValue = current || label;

  return (
    <div className="nav-workspace" ref={rootRef}>
      <button type="button" className="nav-button workspace-trigger" onClick={() => setOpen((prev) => !prev)}>
        <span className="workspace-label">{displayValue}</span>
        <span className="workspace-caret">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div className="workspace-dropdown">
          {history.length > 0 ? (
            history.map((item) => (
              <button key={item} type="button" className="workspace-item" onClick={() => handleSelect(item)}>
                {item}
              </button>
            ))
          ) : (
            <div className="workspace-empty">No workspace saved</div>
          )}
          <button type="button" className="workspace-browse" onClick={async () => {
            setOpen(false);
            await onBrowse();
          }}>
            Browse local
          </button>
        </div>
      )}
    </div>
  );
}
