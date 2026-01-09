export type PackType = "language-pack" | "experience-pack";

export type PackValidationError = {
  path: string;
  code: string;
  message: string;
};

export type PackValidationResult =
  | { valid: true; packType: PackType; data: Record<string, unknown> }
  | { valid: false; errors: PackValidationError[] };

const ID_REGEX = /^[a-z0-9][a-z0-9-_]*$/;
const SEMVER_REGEX = /^\d+\.\d+\.\d+$/;
const COMMAND_ID_REGEX = /^[a-z0-9-_]+$/;
const FAILURE_PATTERN_REGEX = /^[a-z0-9_]+$/;
const FIX_HINT_TRIGGER_REGEX = /^[a-z0-9_]+$/;
const FIX_HINT_ID_REGEX = /^[a-z0-9-_]+$/;
const ERROR_SIGNATURE_REGEX = /^[a-z0-9_]+$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function pushError(errors: PackValidationError[], path: string, code: string, message: string) {
  errors.push({ path, code, message });
}

function validateStringField(
  errors: PackValidationError[],
  value: unknown,
  path: string,
  options: { required?: boolean; minLength?: number; maxLength?: number; pattern?: RegExp; patternHint?: string }
): string | null {
  if (value === undefined || value === null) {
    if (options.required) {
      pushError(errors, path, "REQUIRED", "Field is required");
    }
    return null;
  }
  if (typeof value !== "string") {
    pushError(errors, path, "TYPE", "Expected a string");
    return null;
  }
  const trimmed = value.trim();
  if (options.minLength && trimmed.length < options.minLength) {
    pushError(errors, path, "MIN_LENGTH", `Must be at least ${options.minLength} characters`);
  }
  if (options.maxLength && trimmed.length > options.maxLength) {
    pushError(errors, path, "MAX_LENGTH", `Must be at most ${options.maxLength} characters`);
  }
  if (options.pattern && !options.pattern.test(trimmed)) {
    const reason = options.patternHint ? ` (${options.patternHint})` : "";
    pushError(errors, path, "PATTERN", `Value has invalid format${reason}`);
  }
  return trimmed;
}

function ensureArray(
  errors: PackValidationError[],
  value: unknown,
  path: string,
  options: { required?: boolean; maxItems?: number; minItems?: number }
): unknown[] | null {
  if (value === undefined || value === null) {
    if (options.required) {
      pushError(errors, path, "REQUIRED", "Array is required");
    }
    return null;
  }
  if (!Array.isArray(value)) {
    pushError(errors, path, "TYPE", "Expected an array");
    return null;
  }
  if (options.minItems && value.length < options.minItems) {
    pushError(errors, path, "MIN_ITEMS", `Requires at least ${options.minItems} items`);
  }
  if (options.maxItems && value.length > options.maxItems) {
    pushError(errors, path, "MAX_ITEMS", `Allows at most ${options.maxItems} items`);
  }
  return value;
}

function validateStringArray(
  errors: PackValidationError[],
  value: unknown,
  path: string,
  options: { required?: boolean; maxItems?: number; maxLength?: number; minLength?: number }
) {
  const arr = ensureArray(errors, value, path, { required: options.required, maxItems: options.maxItems });
  if (!arr) return;
  arr.forEach((item, index) => {
    validateStringField(errors, item, `${path}[${index}]`, {
      required: true,
      minLength: options.minLength,
      maxLength: options.maxLength
    });
  });
}

function validateCommandPattern(errors: PackValidationError[], value: unknown, path: string) {
  if (!isRecord(value)) {
    pushError(errors, path, "TYPE", "Expected an object for command pattern");
    return;
  }
  validateStringField(errors, value.id, `${path}.id`, { required: true, pattern: COMMAND_ID_REGEX, minLength: 1 });
  validateStringField(errors, value.regex, `${path}.regex`, { required: true, minLength: 1, maxLength: 512 });
  validateStringField(errors, value.failure_pattern, `${path}.failure_pattern`, {
    required: true,
    pattern: FAILURE_PATTERN_REGEX
  });
  if (value.description !== undefined) {
    validateStringField(errors, value.description, `${path}.description`, { maxLength: 256 });
  }
}

function validateErrorSignature(errors: PackValidationError[], value: unknown, path: string) {
  if (!isRecord(value)) {
    pushError(errors, path, "TYPE", "Expected an object for error signature");
    return;
  }
  validateStringField(errors, value.id, `${path}.id`, { required: true, pattern: ERROR_SIGNATURE_REGEX });
  validateStringField(errors, value.regex, `${path}.regex`, { required: true, minLength: 1, maxLength: 512 });
  validateStringField(errors, value.signature, `${path}.signature`, { required: true, pattern: ERROR_SIGNATURE_REGEX });
  if (value.description !== undefined) {
    validateStringField(errors, value.description, `${path}.description`, { maxLength: 256 });
  }
}

function validateFixHint(errors: PackValidationError[], value: unknown, path: string) {
  if (!isRecord(value)) {
    pushError(errors, path, "TYPE", "Expected an object for fix hint");
    return;
  }
  validateStringField(errors, value.id, `${path}.id`, { required: true, pattern: FIX_HINT_ID_REGEX });
  validateStringField(errors, value.trigger, `${path}.trigger`, { required: true, pattern: FIX_HINT_TRIGGER_REGEX });
  validateStringField(errors, value.trigger_type, `${path}.trigger_type`, {
    required: true
  });
  if (typeof value.trigger_type === "string") {
    if (value.trigger_type !== "failure_pattern" && value.trigger_type !== "error_signature") {
      pushError(errors, `${path}.trigger_type`, "ENUM", "Must be failure_pattern or error_signature");
    }
  }
  const hints = ensureArray(errors, value.hints, `${path}.hints`, { required: true, minItems: 1, maxItems: 20 });
  if (hints) {
    hints.forEach((hint, index) => {
      validateStringField(errors, hint, `${path}.hints[${index}]`, { required: true, maxLength: 512 });
    });
  }
}

function validateCheck(errors: PackValidationError[], value: unknown, path: string) {
  if (!isRecord(value)) {
    pushError(errors, path, "TYPE", "Expected an object for check");
    return;
  }
  const type = validateStringField(errors, value.type, `${path}.type`, { required: true });
  if (type && type !== "command" && type !== "http" && type !== "file") {
    pushError(errors, `${path}.type`, "ENUM", "Type must be command, http, or file");
  }
  if (value.cmd !== undefined) {
    validateStringField(errors, value.cmd, `${path}.cmd`, { required: true, maxLength: 1024 });
  }
  if (value.url !== undefined) {
    const url = validateStringField(errors, value.url, `${path}.url`, { required: true, maxLength: 512 });
    if (url) {
      try {
        new URL(url);
      } catch {
        pushError(errors, `${path}.url`, "PATTERN", "Must be a valid URL");
      }
    }
  }
  if (value.path !== undefined) {
    validateStringField(errors, value.path, `${path}.path`, { required: true, maxLength: 256 });
  }
  if (value.timeout !== undefined) {
    if (typeof value.timeout !== "number" || !Number.isInteger(value.timeout)) {
      pushError(errors, `${path}.timeout`, "TYPE", "Timeout must be an integer");
    } else if (value.timeout < 1 || value.timeout > 300) {
      pushError(errors, `${path}.timeout`, "RANGE", "Timeout must be between 1 and 300 seconds");
    }
  }
}

function validateRule(errors: PackValidationError[], value: unknown, path: string) {
  if (!isRecord(value)) {
    pushError(errors, path, "TYPE", "Expected an object for rule");
    return;
  }
  validateStringField(errors, value.content, `${path}.content`, { required: true, minLength: 1, maxLength: 1024 });
  if (value.scope !== undefined) {
    validateStringField(errors, value.scope, `${path}.scope`, { maxLength: 128 });
  }
  if (value.category !== undefined) {
    validateStringField(errors, value.category, `${path}.category`, { maxLength: 64 });
  }
}

function validateLesson(errors: PackValidationError[], value: unknown, path: string) {
  if (!isRecord(value)) {
    pushError(errors, path, "TYPE", "Expected an object for lesson");
    return;
  }
  validateStringField(errors, value.lesson, `${path}.lesson`, { required: true, minLength: 1, maxLength: 1024 });
  if (value.triggers !== undefined) {
    const triggers = ensureArray(errors, value.triggers, `${path}.triggers`, { minItems: 1, maxItems: 10 });
    if (triggers) {
      triggers.forEach((trigger, index) => {
        if (!isRecord(trigger)) {
          pushError(errors, `${path}.triggers[${index}]`, "TYPE", "Expected an object for trigger");
          return;
        }
        validateStringField(errors, trigger.type, `${path}.triggers[${index}].type`, { required: true });
        if (typeof trigger.type === "string") {
          if (trigger.type !== "file_pattern" && trigger.type !== "file_extension" && trigger.type !== "error_signature") {
            pushError(errors, `${path}.triggers[${index}].type`, "ENUM", "Trigger type must be file_pattern, file_extension, or error_signature");
          }
        }
        validateStringField(errors, trigger.value, `${path}.triggers[${index}].value`, { required: true, maxLength: 128 });
      });
    }
  }
  if (value.suggested_check !== undefined) {
    validateCheck(errors, value.suggested_check, `${path}.suggested_check`);
  }
  if (value.confidence !== undefined) {
    if (typeof value.confidence !== "number") {
      pushError(errors, `${path}.confidence`, "TYPE", "Confidence must be a number");
    } else if (value.confidence < 0 || value.confidence > 1) {
      pushError(errors, `${path}.confidence`, "RANGE", "Confidence must be between 0 and 1");
    }
  }
}

function validateLanguagePackPayload(payload: Record<string, unknown>): PackValidationError[] {
  const errors: PackValidationError[] = [];
  validateStringField(errors, payload.id, "id", {
    required: true,
    minLength: 2,
    maxLength: 64,
    pattern: ID_REGEX
  });
  validateStringField(errors, payload.name, "name", { required: true, minLength: 1, maxLength: 128 });
  validateStringField(errors, payload.version, "version", { required: true, pattern: SEMVER_REGEX, patternHint: "semver" });
  validateStringField(errors, payload.description, "description", { required: true, maxLength: 1024 });
  if (payload.author !== undefined) {
    validateStringField(errors, payload.author, "author", { maxLength: 128 });
  }
  validateStringArray(errors, payload.tags, "tags", { maxItems: 20, maxLength: 32 });
  validateStringArray(errors, payload.detect_patterns, "detect_patterns", { maxItems: 50, maxLength: 128 });
  validateStringArray(errors, payload.project_types, "project_types", { maxItems: 20, maxLength: 32 });
  const cmdPatterns = ensureArray(errors, payload.command_patterns, "command_patterns", { maxItems: 200 });
  if (cmdPatterns) {
    cmdPatterns.forEach((item, index) => validateCommandPattern(errors, item, `command_patterns[${index}]`));
  }
  const errorSignatures = ensureArray(errors, payload.error_signatures, "error_signatures", { maxItems: 500 });
  if (errorSignatures) {
    errorSignatures.forEach((item, index) => validateErrorSignature(errors, item, `error_signatures[${index}]`));
  }
  const fixHints = ensureArray(errors, payload.fix_hints, "fix_hints", { maxItems: 200 });
  if (fixHints) {
    fixHints.forEach((item, index) => validateFixHint(errors, item, `fix_hints[${index}]`));
  }
  return errors;
}

function validateExperiencePackPayload(payload: Record<string, unknown>): PackValidationError[] {
  const errors: PackValidationError[] = [];
  validateStringField(errors, payload.id, "id", {
    required: true,
    minLength: 2,
    maxLength: 64,
    pattern: ID_REGEX
  });
  validateStringField(errors, payload.name, "name", { required: true, minLength: 1, maxLength: 128 });
  validateStringField(errors, payload.version, "version", { required: true, pattern: SEMVER_REGEX, patternHint: "semver" });
  if (payload.description !== undefined) {
    validateStringField(errors, payload.description, "description", { maxLength: 1024 });
  }
  if (payload.author !== undefined) {
    validateStringField(errors, payload.author, "author", { maxLength: 128 });
  }
  validateStringArray(errors, payload.tags, "tags", { maxItems: 20, maxLength: 32 });
  validateStringArray(errors, payload.project_types, "project_types", { maxItems: 20, maxLength: 32 });
  validateStringArray(errors, payload.file_patterns, "file_patterns", { maxItems: 50, maxLength: 128 });
  const rules = ensureArray(errors, payload.rules, "rules", { maxItems: 200 });
  if (rules) {
    rules.forEach((item, index) => validateRule(errors, item, `rules[${index}]`));
  }
  const checks = ensureArray(errors, payload.extra_checks, "extra_checks", { maxItems: 100 });
  if (checks) {
    checks.forEach((item, index) => {
      if (!isRecord(item)) {
        pushError(errors, `extra_checks[${index}]`, "TYPE", "Expected an object for extra check");
        return;
      }
      validateCheck(errors, item.check, `extra_checks[${index}].check`);
      if (item.scope !== undefined) {
        validateStringField(errors, item.scope, `extra_checks[${index}].scope`, { maxLength: 128 });
      }
    });
  }
  const lessons = ensureArray(errors, payload.lessons, "lessons", { maxItems: 100 });
  if (lessons) {
    lessons.forEach((item, index) => validateLesson(errors, item, `lessons[${index}]`));
  }
  return errors;
}

function detectPackType(payload: Record<string, unknown>): PackType | null {
  const explicit = payload.pack_type;
  if (explicit === "language-pack" || explicit === "experience-pack") {
    return explicit;
  }
  const langFields = ["command_patterns", "error_signatures", "fix_hints", "detect_patterns", "project_types"].some((key) =>
    Array.isArray(payload[key])
  );
  const expFields = ["rules", "extra_checks", "lessons", "file_patterns"].some((key) => Array.isArray(payload[key]));
  if (langFields && !expFields) {
    return "language-pack";
  }
  if (expFields && !langFields) {
    return "experience-pack";
  }
  return null;
}

export function validatePack(payload: unknown): PackValidationResult {
  if (!isRecord(payload)) {
    return {
      valid: false,
      errors: [
        {
          path: "",
          code: "TYPE",
          message: "Pack must be an object"
        }
      ]
    };
  }
  const packType = detectPackType(payload);
  if (!packType) {
    return {
      valid: false,
      errors: [
        {
          path: "",
          code: "UNKNOWN_TYPE",
          message: "Unable to determine pack type"
        }
      ]
    };
  }
  const errors = packType === "language-pack" ? validateLanguagePackPayload(payload) : validateExperiencePackPayload(payload);
  if (errors.length > 0) {
    return {
      valid: false,
      errors
    };
  }
  return {
    valid: true,
    packType,
    data: payload
  };
}
