from __future__ import annotations

from .types import CommandPattern, ErrorSignature, FixHint, LanguagePack, PackSource


PYTHON_PACK = LanguagePack(
    id="python",
    name="Python",
    version="1.0.0",
    description="Python language error patterns",
    source=PackSource.BUILTIN,
    detect_patterns=["*.py", "pyproject.toml", "requirements.txt", "setup.py"],
    project_types=["python", "django", "flask", "fastapi"],
    command_patterns=[
        CommandPattern(id="py-pytest", regex=r"\b(pytest|py\.test)\b", failure_pattern="python_test"),
        CommandPattern(id="py-unittest", regex=r"\bpython\s+-m\s+unittest\b", failure_pattern="python_test"),
        CommandPattern(id="py-mypy", regex=r"\b(mypy|python\s+-m\s+mypy)\b", failure_pattern="python_typecheck"),
        CommandPattern(id="py-flake8", regex=r"\bflake8\b", failure_pattern="python_lint"),
        CommandPattern(id="py-black", regex=r"\bblack\s+--check\b", failure_pattern="python_format"),
        CommandPattern(id="py-pip", regex=r"\bpip\s+install\b", failure_pattern="python_install"),
    ],
    error_signatures=[
        ErrorSignature(id="py-import", regex=r"(ModuleNotFoundError|ImportError)", signature="python_import_error"),
        ErrorSignature(id="py-syntax", regex=r"SyntaxError:", signature="python_syntax_error"),
        ErrorSignature(id="py-type", regex=r"TypeError:", signature="python_type_error"),
        ErrorSignature(id="py-attr", regex=r"AttributeError:", signature="python_attribute_error"),
        ErrorSignature(id="py-key", regex=r"KeyError:", signature="python_key_error"),
        ErrorSignature(id="py-assert", regex=r"AssertionError", signature="python_assertion_error"),
    ],
    fix_hints=[
        FixHint(
            id="py-hint-import",
            trigger="python_import_error",
            trigger_type="error_signature",
            hints=["run pip install <package>", "check import paths", "confirm virtualenv is active"],
        ),
        FixHint(
            id="py-hint-syntax",
            trigger="python_syntax_error",
            trigger_type="error_signature",
            hints=["check indentation", "check bracket pairing", "check colons"],
        ),
    ],
)

JAVA_PACK = LanguagePack(
    id="java",
    name="Java",
    version="1.0.0",
    description="Java language error patterns",
    source=PackSource.BUILTIN,
    detect_patterns=["*.java", "pom.xml", "build.gradle", "build.gradle.kts"],
    project_types=["java", "spring", "maven", "gradle"],
    command_patterns=[
        CommandPattern(id="java-mvn", regex=r"\bmvn\b", failure_pattern="java_maven"),
        CommandPattern(id="java-gradle", regex=r"\bgradle\b", failure_pattern="java_gradle"),
    ],
    error_signatures=[
        ErrorSignature(id="java-symbol", regex=r"cannot find symbol", signature="java_symbol_error"),
        ErrorSignature(id="java-exception", regex=r"Exception in thread", signature="java_exception"),
        ErrorSignature(id="java-compile", regex=r"Compilation failed", signature="java_compile_error"),
    ],
    fix_hints=[
        FixHint(
            id="java-hint-symbol",
            trigger="java_symbol_error",
            trigger_type="error_signature",
            hints=["check imports", "verify classpath", "run mvn/gradle clean build"],
        ),
    ],
)

NODE_PACK = LanguagePack(
    id="nodejs",
    name="Node.js",
    version="1.0.0",
    description="Node.js language error patterns",
    source=PackSource.BUILTIN,
    detect_patterns=["package.json", "*.js", "*.ts"],
    project_types=["node", "react", "vue", "angular"],
    command_patterns=[
        CommandPattern(id="node-npm", regex=r"\bnpm\s+(run|install)\b", failure_pattern="node_npm"),
        CommandPattern(id="node-yarn", regex=r"\byarn\s+(run|install)\b", failure_pattern="node_yarn"),
        CommandPattern(id="node-pnpm", regex=r"\bpnpm\s+(run|install)\b", failure_pattern="node_pnpm"),
    ],
    error_signatures=[
        ErrorSignature(id="node-module", regex=r"Cannot find module", signature="node_module_missing"),
        ErrorSignature(id="node-type", regex=r"TypeError:", signature="node_type_error"),
    ],
    fix_hints=[
        FixHint(
            id="node-hint-module",
            trigger="node_module_missing",
            trigger_type="error_signature",
            hints=["run npm install", "verify node_modules", "check import path"],
        ),
    ],
)

BUILTIN_PACKS = [PYTHON_PACK, JAVA_PACK, NODE_PACK]
