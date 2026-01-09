import React from "react";
import { ExperiencePackView } from "../utils/parsers/experiencePackParser";
import { LanguagePackView } from "../utils/parsers/languagePackParser";
import { useI18n } from "../lib/useI18n";

type StructuredPackViewProps = {
  data: LanguagePackView | ExperiencePackView;
  type: "language" | "experience";
};

export function StructuredPackView({ data, type }: StructuredPackViewProps) {
  const { t } = useI18n();
  if (type === "language") {
    const pack = data as LanguagePackView;
    return (
      <div className="structured-view">
        <section className="structured-section">
          <h3>{t.labels.info}</h3>
          <div className="structured-grid">
            <div><span>{t.labels.name}</span>{pack.header.name}</div>
            <div><span>{t.labels.version}</span>{pack.header.version || "-"}</div>
            <div><span>{t.labels.source}</span>{pack.header.source || "-"}</div>
            <div><span>{t.labels.author}</span>{pack.header.author || "-"}</div>
          </div>
          {pack.header.description && <p className="muted">{pack.header.description}</p>}
          {pack.header.tags?.length ? <div className="meta">{t.labels.tags}: {pack.header.tags.join(", ")}</div> : null}
        </section>
        <section className="structured-section">
          <h3>{t.labels.applicability}</h3>
          <div className="structured-grid">
            <div><span>{t.labels.projectTypes}</span>{pack.applicability.projectTypes.join(", ") || "-"}</div>
            <div><span>{t.labels.detectPatterns}</span>{pack.applicability.detectPatterns.join(", ") || "-"}</div>
          </div>
        </section>
        <section className="structured-section">
          <h3>{t.labels.commandPatterns}</h3>
          <div className="list compact">
            {pack.commandPatterns.map((p, idx) => (
              <div key={idx} className="list-item">
                <span className="pill">{p.failurePattern}</span>
              </div>
            ))}
            {!pack.commandPatterns.length && <div className="muted">{t.messages.noCommandPatterns}</div>}
          </div>
        </section>
        <section className="structured-section">
          <h3>{t.labels.errorSignatures}</h3>
          <div className="list compact">
            {pack.errorSignatures.map((s, idx) => (
              <div key={idx} className="list-item">
                <div>
                  <div className="title">{s.regex}</div>
                  <div className="meta">{s.description || "-"}</div>
                </div>
                <span className="pill">{s.signature}</span>
              </div>
            ))}
            {!pack.errorSignatures.length && <div className="muted">{t.messages.noErrorSignatures}</div>}
          </div>
        </section>
        <section className="structured-section">
          <h3>{t.labels.fixHints}</h3>
          <div className="list compact">
            {pack.fixHints.map((h, idx) => (
              <div key={idx} className="list-item">
                <div>
                  <div className="title">{h.trigger}</div>
                  <div className="meta">{h.triggerType}</div>
                  {h.hints?.length ? (
                    <ul className="mini-list">
                      {h.hints.map((hint, hi) => <li key={hi}>{hint}</li>)}
                    </ul>
                  ) : null}
                </div>
              </div>
            ))}
            {!pack.fixHints.length && <div className="muted">{t.messages.noFixHints}</div>}
          </div>
        </section>
        <section className="structured-section">
          <h3>{t.labels.stats}</h3>
          <div className="structured-grid">
            <div><span>{t.labels.commandPatterns}</span>{pack.stats.commandPatterns}</div>
            <div><span>{t.labels.errorSignatures}</span>{pack.stats.errorSignatures}</div>
            <div><span>{t.labels.fixHints}</span>{pack.stats.fixHints}</div>
          </div>
        </section>
      </div>
    );
  }

  const pack = data as ExperiencePackView;
  return (
    <div className="structured-view">
      <section className="structured-section">
        <h3>{t.labels.info}</h3>
        <div className="structured-grid">
          <div><span>{t.labels.name}</span>{pack.header.name}</div>
          <div><span>{t.labels.version}</span>{pack.header.version || "-"}</div>
          <div><span>{t.labels.author}</span>{pack.header.author || "-"}</div>
          <div><span>{t.labels.tags}</span>{pack.header.tags.join(", ") || "-"}</div>
        </div>
        {pack.header.description && <p className="muted">{pack.header.description}</p>}
        {pack.importInfo && (
          <div className="structured-grid">
            <div><span>{t.labels.source}</span>{pack.importInfo.source || "-"}</div>
            <div><span>{t.labels.enabled}</span>{pack.importInfo.enabled ? t.labels.yes : t.labels.no}</div>
          </div>
        )}
      </section>
      <section className="structured-section">
        <h3>{t.labels.rules}</h3>
        <div className="list compact">
          {pack.rules.map((r, idx) => (
            <div key={idx} className="list-item">
              <div>
                <div className="title">{r.content}</div>
                <div className="meta">{r.scope || "-"} {r.category ? `· ${r.category}` : ""}</div>
              </div>
            </div>
          ))}
          {!pack.rules.length && <div className="muted">{t.messages.noRules}</div>}
        </div>
      </section>
      <section className="structured-section">
        <h3>{t.labels.extraChecks}</h3>
        <div className="list compact">
          {pack.extraChecks.map((c, idx) => (
            <div key={idx} className="list-item">
              <div>
                <div className="title">{c.cmd}</div>
                <div className="meta">{c.scope || "-"}</div>
              </div>
            </div>
          ))}
          {!pack.extraChecks.length && <div className="muted">{t.messages.noChecks}</div>}
        </div>
      </section>
      <section className="structured-section">
        <h3>{t.labels.lessons}</h3>
        <div className="list compact">
          {pack.lessons.map((l, idx) => (
            <div key={idx} className="list-item">
              <div>
                <div className="title">{l.content}</div>
                <div className="meta">{l.triggers}</div>
                {l.suggestedCheck ? <div className="meta">Check: {l.suggestedCheck}</div> : null}
              </div>
            </div>
          ))}
          {!pack.lessons.length && <div className="muted">{t.messages.noLessons}</div>}
        </div>
      </section>
      <section className="structured-section">
        <h3>{t.labels.stats}</h3>
        <div className="structured-grid">
          <div><span>{t.labels.rules}</span>{pack.stats.rules}</div>
          <div><span>{t.labels.extraChecks}</span>{pack.stats.extraChecks}</div>
          <div><span>{t.labels.lessons}</span>{pack.stats.lessons}</div>
        </div>
      </section>
    </div>
  );
}
