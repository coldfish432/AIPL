import React from "react";
import { Language } from "../lib/i18n";
import "./LanguageSwitch.css";

interface LanguageSwitchProps {
  language: Language;
  onToggle: () => void;
  className?: string;
}

export function LanguageSwitch({ language, onToggle, className = "" }: LanguageSwitchProps) {
  return (
    <button
      className={`language-switch ${className}`}
      onClick={onToggle}
      title={language === "zh" ? "Switch to English" : "切换到中文"}
      aria-label={language === "zh" ? "Switch to English" : "切换到中文"}
    >
      <span className={`lang-option ${language === "zh" ? "active" : ""}`}>中</span>
      <span className="lang-divider">/</span>
      <span className={`lang-option ${language === "en" ? "active" : ""}`}>EN</span>
    </button>
  );
}

interface LanguageSelectProps {
  language: Language;
  onChange: (lang: Language) => void;
  className?: string;
}

export function LanguageSelect({ language, onChange, className = "" }: LanguageSelectProps) {
  return (
    <select
      className={`language-select ${className}`}
      value={language}
      onChange={(e) => onChange(e.target.value as Language)}
      aria-label="Select language"
    >
      <option value="zh">中文</option>
      <option value="en">English</option>
    </select>
  );
}

export default LanguageSwitch;
