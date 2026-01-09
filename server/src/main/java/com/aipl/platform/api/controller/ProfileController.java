package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.api.dto.request.ProfileUpdateRequest;
import com.aipl.platform.service.ProfileService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/profile")
public class ProfileController {
    private final ProfileService profileService;

    public ProfileController(ProfileService profileService) {
        this.profileService = profileService;
    }

    @GetMapping
    public ApiResponse<JsonNode> get(@RequestParam String workspace) throws Exception {
        JsonNode res = profileService.get(workspace);
        return ApiResponse.ok(res);
    }

    @PatchMapping
    public ApiResponse<JsonNode> update(@RequestBody ProfileUpdateRequest req) throws Exception {
        return handleUpdate(req);
    }

    @PostMapping
    public ApiResponse<JsonNode> updatePost(@RequestBody ProfileUpdateRequest req) throws Exception {
        return handleUpdate(req);
    }

    private ApiResponse<JsonNode> handleUpdate(ProfileUpdateRequest req) throws Exception {
        if (req.workspace == null || req.workspace.isBlank()) {
            return ApiResponse.ok(null);
        }
        JsonNode res = profileService.update(req.workspace, req.user_hard);
        return ApiResponse.ok(res);
    }
}
