package com.aipl.platform.engine;

import java.util.ArrayList;
import java.util.List;

public class EngineCommandBuilder {
    private final List<String> args = new ArrayList<>();

    public EngineCommandBuilder(String baseCommand, String root) {
        args.add("python");
        args.add("engine_cli.py");
        args.add("--root");
        args.add(root);
        args.add(baseCommand);
    }

    public EngineCommandBuilder arg(String key, String value) {
        if (value == null || value.isBlank()) {
            return this;
        }
        args.add(key);
        args.add(value);
        return this;
    }

    public EngineCommandBuilder flag(String flag, boolean enabled) {
        if (enabled) {
            args.add(flag);
        }
        return this;
    }

    public List<String> build() {
        return new ArrayList<>(args);
    }
}
