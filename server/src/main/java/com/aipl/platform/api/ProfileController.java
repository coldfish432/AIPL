package com.aipl.platform.api;

import com.aipl.platform.engine.EngineClient;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/profile")
public class ProfileController {
    private final EngineClient engine;

    public ProfileController(EngineClient engine) {
        this.engine = engine;
    }

    @GetMapping
    public ApiResponse<JsonNode> get(@RequestParam String workspace) throws Exception {
        JsonNode res = engine.profile("get", workspace);
        return ApiResponse.ok(res);
    }

    @PostMapping("/propose")
    public ApiResponse<JsonNode> propose(@RequestBody ProfileRequest req) throws Exception {
        JsonNode res = engine.profile("propose", req.workspace);
        return ApiResponse.ok(res);
    }

    @PostMapping("/approve")
    public ApiResponse<JsonNode> approve(@RequestBody ProfileRequest req) throws Exception {
        JsonNode res = engine.profile("approve", req.workspace);
        return ApiResponse.ok(res);
    }

    @PostMapping("/reject")
    public ApiResponse<JsonNode> reject(@RequestBody ProfileRequest req) throws Exception {
        JsonNode res = engine.profile("reject", req.workspace);
        return ApiResponse.ok(res);
    }
}
