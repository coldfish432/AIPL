package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.ProfileRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
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

    @PostMapping("/propose")
    public ApiResponse<JsonNode> propose(@RequestBody ProfileRequest req) throws Exception {
        JsonNode res = profileService.propose(req.workspace);
        return ApiResponse.ok(res);
    }

    @PostMapping("/approve")
    public ApiResponse<JsonNode> approve(@RequestBody ProfileRequest req) throws Exception {
        JsonNode res = profileService.approve(req.workspace);
        return ApiResponse.ok(res);
    }

    @PostMapping("/reject")
    public ApiResponse<JsonNode> reject(@RequestBody ProfileRequest req) throws Exception {
        JsonNode res = profileService.reject(req.workspace);
        return ApiResponse.ok(res);
    }
}
