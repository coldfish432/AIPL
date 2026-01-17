package com.aipl.platform.service;

import com.aipl.platform.api.dto.request.AssistantChatMessage;
import com.aipl.platform.engine.EngineClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class AssistantService {
    private final EngineClient engine;
    private final ObjectMapper mapper = new ObjectMapper();

    public AssistantService(EngineClient engine) {
        this.engine = engine;
    }

    public JsonNode chat(List<AssistantChatMessage> messages, String messageFallback, String workspace) throws Exception {
        JsonNode payload = buildPayload(messages, messageFallback);
        return engine.assistantChat(payload, workspace);
    }

    public ObjectNode buildPayload(List<AssistantChatMessage> messages, String messageFallback) {
        ObjectNode payload = mapper.createObjectNode();
        ArrayNode arr = payload.putArray("messages");
        if (messages != null) {
            for (AssistantChatMessage msg : messages) {
                if (msg == null || msg.content == null) {
                    continue;
                }
                ObjectNode node = mapper.createObjectNode();
                node.put("role", msg.role == null ? "user" : msg.role);
                node.put("content", msg.content);
                arr.add(node);
            }
        }
        if (arr.isEmpty() && messageFallback != null && !messageFallback.isBlank()) {
            ObjectNode node = mapper.createObjectNode();
            node.put("role", "user");
            node.put("content", messageFallback);
            arr.add(node);
        }
        return payload;
    }

    public String buildTaskFromMessages(List<AssistantChatMessage> messages) {
        if (messages == null || messages.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("User request based on conversation:\n");
        for (AssistantChatMessage msg : messages) {
            if (msg == null || msg.content == null || msg.content.isBlank()) {
                continue;
            }
            String role = msg.role == null ? "user" : msg.role;
            sb.append(role).append(": ").append(msg.content.trim()).append("\n");
        }
        return sb.toString().trim();
    }
}
