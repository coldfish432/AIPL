package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;

@Service
public class ProfileService {
    private final EngineClient engine;

    public ProfileService(EngineClient engine) {
        this.engine = engine;
    }

    public JsonNode get(String workspace) throws Exception {
        return engine.profile("get", workspace);
    }

    public JsonNode propose(String workspace) throws Exception {
        return engine.profile("propose", workspace);
    }

    public JsonNode approve(String workspace) throws Exception {
        return engine.profile("approve", workspace);
    }

    public JsonNode reject(String workspace) throws Exception {
        return engine.profile("reject", workspace);
    }
}
