package com.aipl.platform.api.dto.request;

import java.util.List;

public class AssistantChatRequest {
    public List<AssistantChatMessage> messages;
    public String message;
    public String workspace;
    public String policy;
}
