import React, { useCallback, useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { PackValidationError, PackType, validatePack } from "../utils/packValidation";

type PackDropSuccess = {
  success: true;
  data: Record<string, unknown>;
  fileName: string;
  packType: PackType;
};

type PackDropFailure = {
  success: false;
  error: string;
  errors?: PackValidationError[];
  fileName?: string;
  packType?: PackType;
};

export type PackDropResult = PackDropSuccess | PackDropFailure;

export type PackDropType = "language" | "experience" | "any";

export type PackDropZoneProps = {
  acceptType?: PackDropType;
  onDrop: (result: PackDropResult) => void;
  onError?: (message: string) => void;
  showValidation?: boolean;
  placeholder?: React.ReactNode;
  compact?: boolean;
  className?: string;
  buttonLabel?: string;
};

type UsePackDropOptions = {
  acceptType?: PackDropType;
  onDrop: (result: PackDropResult) => void;
  onError?: (message: string) => void;
};

export function usePackDrop({ acceptType = "any", onDrop, onError }: UsePackDropOptions) {
  const [dragging, setDragging] = useState(false);
  const [lastResult, setLastResult] = useState<PackDropResult | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const processFile = useCallback(
    async (file: File) => {
      const fileName = file.name;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        const validation = validatePack(data);
        if (!validation.valid) {
          const result: PackDropFailure = {
            success: false,
            error: "Pack validation failed",
            errors: validation.errors,
            fileName
          };
          setLastResult(result);
          onDrop(result);
          onError?.(result.error);
          return;
        }
        if (acceptType !== "any" && validation.packType !== `${acceptType}-pack`) {
          const message = `Expected a ${acceptType} pack but got ${validation.packType}`;
          const result: PackDropFailure = {
            success: false,
            error: message,
            fileName,
            packType: validation.packType
          };
          setLastResult(result);
          onDrop(result);
          onError?.(message);
          return;
        }
        const result: PackDropSuccess = {
          success: true,
          data: validation.data,
          fileName,
          packType: validation.packType
        };
        setLastResult(result);
        onDrop(result);
      } catch (err) {
        const message = err instanceof SyntaxError ? "Invalid JSON file" : err instanceof Error ? err.message : "Unable to read file";
        const result: PackDropFailure = {
          success: false,
          error: message,
          fileName
        };
        setLastResult(result);
        onDrop(result);
        onError?.(message);
      }
    },
    [acceptType, onDrop, onError]
  );

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        void processFile(file);
      }
      event.target.value = "";
    },
    [processFile]
  );

  const openFileDialog = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const dropProps = {
    onDragOver: (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(true);
      event.dataTransfer.dropEffect = "copy";
    },
    onDragEnter: (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(true);
    },
    onDragLeave: (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
    },
    onDrop: (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      const file = event.dataTransfer.files?.[0];
      if (file) {
        void processFile(file);
      }
    },
    onClick: () => {
      openFileDialog();
    }
  };

  return {
    dropProps,
    inputRef,
    handleInputChange,
    openFileDialog,
    dragging,
    lastResult
  };
}

export function PackDropZone({
  acceptType = "any",
  onDrop,
  onError,
  showValidation = true,
  placeholder,
  compact = false,
  className,
  buttonLabel
}: PackDropZoneProps) {
  const { dropProps, inputRef, handleInputChange, openFileDialog, dragging, lastResult } = usePackDrop({
    acceptType,
    onDrop,
    onError
  });

  const acceptLabel =
    acceptType === "language"
      ? "Language pack (*.json)"
      : acceptType === "experience"
      ? "Experience pack (*.json)"
      : "Pack file (*.json)";

  return (
    <div
      {...dropProps}
      className={`pack-drop-zone ${dragging ? "dragging" : ""} ${compact ? "compact" : ""} ${className ?? ""}`.trim()}
      tabIndex={0}
      role="button"
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openFileDialog();
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="pack-drop-input"
        onChange={handleInputChange}
      />
      <UploadCloud size={40} className="pack-drop-icon" />
      <p className="pack-drop-title">{placeholder ?? "Drop a pack file here"}</p>
      <p className="pack-drop-subtitle">{acceptLabel}</p>
      <button
        type="button"
        className="pack-drop-button"
        onClick={(event) => {
          event.stopPropagation();
          openFileDialog();
        }}
      >
        {buttonLabel ?? "Select file"}
      </button>
      {showValidation && lastResult && !lastResult.success && (
        <div className="pack-drop-errors">
          <p className="pack-drop-error-title">{lastResult.error}</p>
          {lastResult.errors && lastResult.errors.length > 0 && (
            <ul>
              {lastResult.errors.slice(0, 4).map((err) => (
                <li key={err.path} className="pack-drop-error-item">
                  <span className="pack-drop-error-path">{err.path}</span>
                  <span className="pack-drop-error-message">{err.message}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export const CompactPackDropZone = (props: Omit<PackDropZoneProps, "compact">) => <PackDropZone compact {...props} />;
