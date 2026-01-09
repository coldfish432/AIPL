import React from "react";

type MarkdownRendererProps = {
  content: string;
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return <pre className="pre markdown">{content}</pre>;
}
