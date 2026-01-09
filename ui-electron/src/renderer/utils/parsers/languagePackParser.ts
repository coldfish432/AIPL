export type LanguagePackView = {
  header: {
    name: string;
    description?: string;
    version?: string;
    source?: string;
    author?: string;
    tags: string[];
  };
  applicability: {
    projectTypes: string[];
    detectPatterns: string[];
  };
  commandPatterns: Array<{ regex: string; failurePattern: string; description?: string }>;
  errorSignatures: Array<{ regex: string; signature: string; description?: string }>;
  fixHints: Array<{ trigger: string; triggerType: string; hints: string[] }>;
  stats: {
    commandPatterns: number;
    errorSignatures: number;
    fixHints: number;
  };
};

function simplifyRegex(regex: string): string {
  return String(regex).replace(/\\b/g, "").replace(/\\\./g, ".").replace(/\\/g, "");
}

function formatSource(source: string): string {
  if (!source) return "";
  const map: Record<string, string> = {
    builtin: "Builtin",
    user: "User",
    learned: "Learned"
  };
  return map[source] || source;
}

export class LanguagePackParser {
  static toMarkdown(pack: any): string {
    const lines: string[] = [];
    lines.push(`# ${pack.name || "Language Pack"}`);
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
    if (pack.tags?.length) lines.push(`- **Tags**: ${pack.tags.join(", ")}`);
    lines.push("");

    if (pack.project_types?.length || pack.detect_patterns?.length) {
      lines.push("## Applicability");
      lines.push("");
      if (pack.project_types?.length) lines.push(`- **Project types**: ${pack.project_types.join(", ")}`);
      if (pack.detect_patterns?.length) lines.push(`- **Detect patterns**: ${pack.detect_patterns.join(", ")}`);
      lines.push("");
    }

    if (pack.command_patterns?.length) {
      lines.push("## Command Patterns");
      lines.push("");
      for (const p of pack.command_patterns) {
        lines.push(`- \`${simplifyRegex(p.regex)}\` -> \`${p.failure_pattern}\``);
        if (p.description) lines.push(`  - ${p.description}`);
      }
      lines.push("");
    }

    if (pack.error_signatures?.length) {
      lines.push("## Error Signatures");
      lines.push("");
      for (const s of pack.error_signatures) {
        lines.push(`- \`${simplifyRegex(s.regex)}\` -> \`${s.signature}\``);
        if (s.description) lines.push(`  - ${s.description}`);
      }
      lines.push("");
    }

    if (pack.fix_hints?.length) {
      lines.push("## Fix Hints");
      lines.push("");
      for (const h of pack.fix_hints) {
        lines.push(`### Trigger: \`${h.trigger}\` (${h.trigger_type})`);
        lines.push("");
        for (const hint of h.hints || []) {
          lines.push(`- ${hint}`);
        }
        lines.push("");
      }
    }

    lines.push("## Stats");
    lines.push("");
    lines.push(`- Command patterns: ${pack.command_patterns?.length || 0}`);
    lines.push(`- Error signatures: ${pack.error_signatures?.length || 0}`);
    lines.push(`- Fix hints: ${pack.fix_hints?.length || 0}`);

    return lines.join("\n");
  }

  static toStructured(pack: any): LanguagePackView {
    return {
      header: {
        name: pack.name || "",
        description: pack.description || "",
        version: pack.version || "",
        source: formatSource(pack.source),
        author: pack.author || "",
        tags: pack.tags || []
      },
      applicability: {
        projectTypes: pack.project_types || [],
        detectPatterns: pack.detect_patterns || []
      },
      commandPatterns: (pack.command_patterns || []).map((p: any) => ({
        regex: simplifyRegex(p.regex),
        failurePattern: p.failure_pattern,
        description: p.description || ""
      })),
      errorSignatures: (pack.error_signatures || []).map((s: any) => ({
        regex: simplifyRegex(s.regex),
        signature: s.signature,
        description: s.description || ""
      })),
      fixHints: (pack.fix_hints || []).map((h: any) => ({
        trigger: h.trigger,
        triggerType: h.trigger_type,
        hints: h.hints || []
      })),
      stats: {
        commandPatterns: pack.command_patterns?.length || 0,
        errorSignatures: pack.error_signatures?.length || 0,
        fixHints: pack.fix_hints?.length || 0
      }
    };
  }
}
