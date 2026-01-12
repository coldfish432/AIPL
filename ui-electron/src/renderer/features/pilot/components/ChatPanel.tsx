/**
 * Chat Panel 组件
 * 聊天消息面板
 */

import React, { useEffect, useRef } from "react";
import { Bot, User } from "lucide-react";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import type { ChatMessage } from "@/apis/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading?: boolean;
}

export function ChatPanel({ messages, loading }: ChatPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-panel" ref={containerRef}>
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} message={msg} />
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="chat-message assistant">
            <div className="chat-message-avatar">
              <Bot size={18} />
            </div>
            <div className="chat-message-content">
              <div className="chat-typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// 单条消息
interface ChatMessageProps {
  message: ChatMessage;
}

function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="chat-message system">
        <div className="chat-message-content system">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`chat-message ${isUser ? "user" : "assistant"}`}>
      <div className="chat-message-avatar">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className="chat-message-content">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <MarkdownRenderer content={message.content} />
        )}
      </div>
    </div>
  );
}
