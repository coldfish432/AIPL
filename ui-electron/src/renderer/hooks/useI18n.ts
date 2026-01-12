/**
 * 国际化 Hook
 */

import { useCallback, useEffect, useState } from "react";
import { STORAGE_KEYS } from "@/config/settings";
import { translations, Language } from "@/i18n";

// ============================================================
// Constants
// ============================================================

export const LANGUAGE_CHANGE_EVENT = "aipl-language-changed";

// ============================================================
// Types
// ============================================================

export type { Language };

export interface UseI18nReturn {
  language: Language;
  t: typeof translations.zh;
  toggleLanguage: () => void;
  setLanguage: (lang: Language) => void;
}

// ============================================================
// Helpers
// ============================================================

function getStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.languageKey);
    if (stored === "en" || stored === "zh") {
      return stored;
    }
  } catch {
    // Ignore storage errors
  }
  return "zh";
}

function storeLanguage(lang: Language): void {
  try {
    localStorage.setItem(STORAGE_KEYS.languageKey, lang);
  } catch {
    // Ignore storage errors
  }
}

// ============================================================
// Hook
// ============================================================

export function useI18n(): UseI18nReturn {
  const [language, setLanguageState] = useState<Language>(() => getStoredLanguage());

  // Sync across tabs
  useEffect(() => {
    const handleChange = () => {
      setLanguageState(getStoredLanguage());
    };

    window.addEventListener(LANGUAGE_CHANGE_EVENT, handleChange);
    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEYS.languageKey) {
        handleChange();
      }
    });

    return () => {
      window.removeEventListener(LANGUAGE_CHANGE_EVENT, handleChange);
    };
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    storeLanguage(lang);
    window.dispatchEvent(new Event(LANGUAGE_CHANGE_EVENT));
  }, []);

  const toggleLanguage = useCallback(() => {
    const next = language === "zh" ? "en" : "zh";
    setLanguage(next);
  }, [language, setLanguage]);

  const t = translations[language];

  return {
    language,
    t,
    toggleLanguage,
    setLanguage,
  };
}
