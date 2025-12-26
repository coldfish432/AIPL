package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.PlanRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.PlanService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
public class PlanController {
    private final PlanService planService;

    public PlanController(PlanService planService) {
        this.planService = planService;
    }

    @PostMapping("/plans")
    public ApiResponse<JsonNode> plan(@RequestBody PlanRequest req) throws Exception {
        JsonNode res = planService.plan(req.task, req.planId, req.workspace);
        return ApiResponse.ok(res);
    }

    @GetMapping("/plans")
    public ApiResponse<List<JsonNode>> listPlans() throws Exception {
        return ApiResponse.ok(planService.listPlans());
    }

    @GetMapping("/plans/{planId}")
    public ApiResponse<JsonNode> planDetail(@PathVariable String planId) throws Exception {
        return ApiResponse.ok(planService.planDetail(planId));
    }
}
