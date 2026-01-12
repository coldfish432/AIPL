/**
 * Markdown Renderer 组件
 * 渲染 Markdown 内容
 */

import React, { useMemo } from "react";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  const html = useMemo(() => parseMarkdown(content), [content]);

  return (
    <div
      className={`markdown-content ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// 简单的 Markdown 解析器
function parseMarkdown(text: string): string {
  if (!text) return "";

  let html = escapeHtml(text);

  // 代码块
  html = html.replace(
    /```(\w+)?\n([\s\S]*?)```/g,
    (_, lang, code) => {
      return `<pre class="code-block${lang ? ` language-${lang}` : ""}"><code>${code.trim()}</code></pre>`;
    }
  );

  // 行内代码
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // 粗体
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // 斜体
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  // 链接
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );

  // 标题
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // 列表项
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

  // 有序列表
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

  // 换行
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");

  // 包装段落
  if (!html.startsWith("<")) {
    html = `<p>${html}</p>`;
  }

  return html;
}

// HTML 转义
function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}
