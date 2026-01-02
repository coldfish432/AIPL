package com.aipl.platform.api.dto.request;

import java.util.List;

public class AssistantPlanRequest {
    public List<AssistantChatMessage> messages;
    public String planId;
    public String workspace;
}
