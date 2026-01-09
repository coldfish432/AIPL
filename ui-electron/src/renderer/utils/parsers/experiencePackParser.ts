export type ExperiencePackView = {
  header: {
    name: string;
    description?: string;
    version?: string;
    author?: string;
    tags: string[];
  };
  importInfo?: {
    source?: string;
    enabled?: boolean;
  };
  rules: Array<{ content: string; scope?: string; category?: string }>;
  extraChecks: Array<{ cmd: string; scope?: string }>;
  lessons: Array<{ content: string; triggers: string; suggestedCheck?: string; confidence?: number }>;
  stats: {
    rules: number;
    extraChecks: number;
    lessons: number;
  };
};

function formatSource(source: string): string {
  if (!source) return "";
  const map: Record<string, string> = {
    file: "File",
    url: "URL",
    workspace: "Workspace"
  };
  return map[source] || source;
}

function formatTriggers(triggers: any[]): string {
  const parts: string[] = [];
  for (const t of triggers || []) {
    if (!t || typeof t !== "object") continue;
    if (t.type === "file_pattern") parts.push(`file ${t.value}`);
    else if (t.type === "file_extension") parts.push(`ext ${t.value}`);
    else parts.push(`${t.type}: ${t.value}`);
  }
  return parts.join(" | ") || "-";
}

export class ExperiencePackParser {
  static toMarkdown(pack: any): string {
    const lines: string[] = [];
    lines.push(`# ${pack.name || "Experience Pack"}`);
    lines.push("");
    if (pack.description) {
      lines.push(`> ${pack.description}`);
      lines.push("");
    }

    lines.push("## Info");
    lines.push("");
    lines.push(`- **ID**: \`${pack.id || ""}\``);
    lines.push(`- **Version**: ${pack.version || ""}`);
    if (pack.author) lines.push(`- **Author**: ${pack.author}`);
    if (pack.source) lines.push(`- **Source**: ${formatSource(pack.source)}`);
    if (typeof pack.enabled === "boolean") lines.push(`- **Enabled**: ${pack.enabled ? "Yes" : "No"}`);
    lines.push("");

    if (pack.rules?.length) {
      lines.push("## Rules");
      lines.push("");
      pack.rules.forEach((r: any, idx: number) => {
        const scope = r.scope ? ` (${r.scope})` : "";
        const category = r.category ? `[${r.category}] ` : "";
        lines.push(`${idx + 1}. ${category}${r.content}${scope}`);
      });
      lines.push("");
    }

    if (pack.extra_checks?.length) {
      lines.push("## Extra Checks");
      lines.push("");
      lines.push("| Command | Scope |");
      lines.push("|---|---|");
      for (const check of pack.extra_checks) {
        const cmd = check.check?.cmd || JSON.stringify(check.check || {});
        const scope = check.scope || "all";
        lines.push(`| \`${cmd}\` | ${scope} |`);
      }
      lines.push("");
    }

    if (pack.lessons?.length) {
      lines.push("## Lessons");
      lines.push("");
      pack.lessons.forEach((l: any, idx: number) => {
        lines.push(`### ${idx + 1}. ${l.lesson}`);
        lines.push("");
        if (l.triggers?.length) {
          lines.push(`**Triggers**: ${formatTriggers(l.triggers)}`);
          lines.push("");
        }
        if (l.suggested_check?.cmd) {
          lines.push(`**Suggested check**: \`${l.suggested_check.cmd}\``);
          lines.push("");
        }
        if (l.confidence !== undefined) {
          lines.push(`*Confidence ${Math.round(l.confidence * 100)}%*`);
          lines.push("");
        }
      });
    }

    lines.push("## Stats");
    lines.push("");
    lines.push(`- Rules: ${pack.rules?.length || 0}`);
    lines.push(`- Extra checks: ${pack.extra_checks?.length || 0}`);
    lines.push(`- Lessons: ${pack.lessons?.length || 0}`);

    return lines.join("\n");
  }

  static toStructured(pack: any): ExperiencePackView {
    const isImported = "source" in pack && "imported_at" in pack;
    return {
      header: {
        name: pack.name || "",
        description: pack.description || "",
        version: pack.version || "",
        author: pack.author || "",
        tags: pack.tags || []
      },
      importInfo: isImported
        ? {
            source: formatSource(pack.source),
            enabled: pack.enabled !== false
          }
        : undefined,
      rules: (pack.rules || []).map((r: any) => ({
        content: r.content,
        scope: r.scope,
        category: r.category
      })),
      extraChecks: (pack.extra_checks || []).map((c: any) => ({
        cmd: c.check?.cmd || JSON.stringify(c.check || {}),
        scope: c.scope
      })),
      lessons: (pack.lessons || []).map((l: any) => ({
        content: l.lesson,
        triggers: formatTriggers(l.triggers || []),
        suggestedCheck: l.suggested_check?.cmd,
        confidence: l.confidence
      })),
      stats: {
        rules: pack.rules?.length || 0,
        extraChecks: pack.extra_checks?.length || 0,
        lessons: pack.lessons?.length || 0
      }
    };
  }
}
