import { ExperiencePackParser } from "./experiencePackParser";
import { LanguagePackParser } from "./languagePackParser";

export type PackType = "language" | "experience";

export function parsePack(data: any, type: PackType) {
  if (type === "language") {
    return {
      markdown: LanguagePackParser.toMarkdown(data),
      structured: LanguagePackParser.toStructured(data)
    };
  }
  return {
    markdown: ExperiencePackParser.toMarkdown(data),
    structured: ExperiencePackParser.toStructured(data)
  };
}
