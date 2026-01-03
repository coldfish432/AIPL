import { useCallback, useEffect, useState } from "react";
import {
  Language,
  LANGUAGE_CHANGE_EVENT,
  TranslationKeys,
  getLabels,
  getStoredLanguage,
  setStoredLanguage
} from "./i18n";

interface UseI18nReturn {
  language: Language;
  t: TranslationKeys;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
}

export function useI18n(): UseI18nReturn {
  const [language, setLanguageState] = useState<Language>(() => getStoredLanguage());
  const [t, setT] = useState<TranslationKeys>(() => getLabels(language));

  useEffect(() => {
    const handleLanguageChange = (event: Event) => {
      const customEvent = event as CustomEvent<Language>;
      const newLang = customEvent.detail;
      setLanguageState(newLang);
      setT(getLabels(newLang));
    };

    window.addEventListener(LANGUAGE_CHANGE_EVENT, handleLanguageChange);
    return () => {
      window.removeEventListener(LANGUAGE_CHANGE_EVENT, handleLanguageChange);
    };
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    setStoredLanguage(lang);
    setLanguageState(lang);
    setT(getLabels(lang));
  }, []);

  const toggleLanguage = useCallback(() => {
    const newLang = language === "zh" ? "en" : "zh";
    setLanguage(newLang);
  }, [language, setLanguage]);

  return {
    language,
    t,
    setLanguage,
    toggleLanguage
  };
}

export default useI18n;
