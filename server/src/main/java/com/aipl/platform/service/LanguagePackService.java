package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;

@Service
public class LanguagePackService {
    private final EngineClient engine;

    public LanguagePackService(EngineClient engine) {
        this.engine = engine;
    }

    public JsonNode list(String workspace) throws Exception {
        return engine.languagePacks("list", null, null, null, null, null, workspace);
    }

    public JsonNode get(String packId) throws Exception {
        return engine.languagePacks("get", packId, null, null, null, null, null);
    }

    public JsonNode importPack(JsonNode pack) throws Exception {
        return engine.languagePacks("import", null, pack, null, null, null, null);
    }

    public JsonNode export(String packId) throws Exception {
        return engine.languagePacks("export", packId, null, null, null, null, null);
    }

    public JsonNode exportMerged(String packId, String name, String description) throws Exception {
        return engine.languagePacks("export-merged", packId, null, name, description, null, null);
    }

    public JsonNode exportLearned(String name, String description) throws Exception {
        return engine.languagePacks("learned-export", null, null, name, description, null, null);
    }

    public JsonNode delete(String packId) throws Exception {
        return engine.languagePacks("delete", packId, null, null, null, null, null);
    }

    public JsonNode update(String packId, Boolean enabled) throws Exception {
        return engine.languagePacks("update", packId, null, null, null, enabled, null);
    }

    public JsonNode clearLearned() throws Exception {
        return engine.languagePacks("learned-clear", null, null, null, null, null, null);
    }
}
