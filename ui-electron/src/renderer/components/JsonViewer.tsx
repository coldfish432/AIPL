import React from "react";

type JsonViewerProps = {
  data: unknown;
};

export function JsonViewer({ data }: JsonViewerProps) {
  return <pre className="pre">{JSON.stringify(data, null, 2)}</pre>;
}
