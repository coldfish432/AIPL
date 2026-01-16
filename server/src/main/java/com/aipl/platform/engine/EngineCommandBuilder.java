package com.aipl.platform.engine;

import java.util.ArrayList;
import java.util.List;

public class EngineCommandBuilder {
    private final List<String> baseArgs = new ArrayList<>();
    private final List<String> subArgs = new ArrayList<>();
    private final String subCommand;

    public EngineCommandBuilder(String baseCommand, String root) {
        baseArgs.add("python");
        baseArgs.add("engine_cli.py");
        baseArgs.add("--root");
        baseArgs.add(root);
        this.subCommand = baseCommand;
    }

    /**
     * Add an argument that should appear before the subcommand (global scope).
     */
    public EngineCommandBuilder globalArg(String key, String value) {
        if (value == null || value.isBlank()) {
            return this;
        }
        baseArgs.add(key);
        baseArgs.add(value);
        return this;
    }

    /**
     * Add an argument that belongs to the subcommand.
     */
    public EngineCommandBuilder arg(String key, String value) {
        if (value == null || value.isBlank()) {
            return this;
        }
        subArgs.add(key);
        subArgs.add(value);
        return this;
    }

    public EngineCommandBuilder flag(String flag, boolean enabled) {
        if (enabled) {
            subArgs.add(flag);
        }
        return this;
    }

    public List<String> build() {
        List<String> result = new ArrayList<>(baseArgs);
        result.add(subCommand);
        result.addAll(subArgs);
        return result;
    }
}
