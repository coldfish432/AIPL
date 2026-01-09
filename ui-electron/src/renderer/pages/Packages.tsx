import React from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { useI18n } from "../lib/useI18n";

export function PackagesHome() {
  const { t } = useI18n();
  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{t.labels.packageIntroTitle}</h2>
      </div>
      <div className="panel-content">
        <p className="page-muted">{t.messages.packageIntro}</p>
      </div>
    </div>
  );
}

export default function PackagesLayout() {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="page-subtitle">{t.labels.packageSubtitle}</p>
        </div>
        <div className="page-actions">
          <button className="button-primary" onClick={() => navigate("language")}>
            {t.labels.languagePack}
          </button>
          <button className="button-secondary" onClick={() => navigate("experience")}>
            {t.labels.experiencePack}
          </button>
        </div>
      </div>
      <Outlet />
    </section>
  );
}
