import { useCallback, useRef, useEffect } from "react";
import { useAppStore } from "../stores/appStore";
import { sendChatMessage, ApiError } from "../services/api";
import type { ChatMessage } from "../types";

const now = () =>
  new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export function useChat() {
  const {
    chatMessages,
    setChatMessages,
    isChatLoading,
    setIsChatLoading,
    sessionId,
    setSessionId,
  } = useAppStore();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages, isChatLoading]);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isChatLoading) return;

      const userMsg: ChatMessage = {
        id: "u-" + Date.now(),
        role: "user",
        text: text.trim(),
        timestamp: now(),
      };
      setChatMessages((prev) => [...prev, userMsg]);
      setIsChatLoading(true);

      try {
        // Only the message and the session id go over the wire. The backend owns the
        // conversation history; `chatMessages` here is a render list, not the transcript
        // the model sees. Sending it too would duplicate every turn and double the bill.
        const res = await sendChatMessage(text, sessionId);

        // The backend mints a session on the first turn when none was supplied, and quietly
        // replaces an expired one. Adopt whatever came back rather than assuming it matched.
        if (res.session_id !== sessionId) setSessionId(res.session_id);

        setChatMessages((prev) => [
          ...prev,
          {
            id: "ai-" + Date.now(),
            role: "assistant",
            text: res.reply,
            timestamp: now(),
            toolCalls: res.tool_calls,
            groundedInAnalysis: res.grounded_in_analysis,
          },
        ]);
      } catch (err) {
        // Shown in the transcript, styled as an error, and never disguised as a reply. A
        // budget ceiling or an unreachable backend has to be legible as a system failure —
        // an assistant-looking bubble saying something plausible is exactly the confusion
        // the mock fallback used to cause.
        const msg =
          err instanceof ApiError
            ? err.message
            : "Unable to reach the assistant. Please retry.";
        setChatMessages((prev) => [
          ...prev,
          {
            id: "err-" + Date.now(),
            role: "system",
            text: msg,
            timestamp: now(),
            isError: true,
          },
        ]);
      } finally {
        setIsChatLoading(false);
      }
    },
    [isChatLoading, sessionId, setChatMessages, setIsChatLoading, setSessionId]
  );

  return { messages: chatMessages, send, isChatLoading, scrollRef };
}
