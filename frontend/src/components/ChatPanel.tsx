import { useState, useRef } from "react";
import { Send, Paperclip, Mic, Square } from "lucide-react";
import { useChat } from "../hooks/useChat";
import ChatMessage from "./ChatMessage";
import { PanelHeader } from "./UploadPanel";

interface ChatPanelProps {
  number?: string;
  showHeader?: boolean;
  embedded?: boolean;
}

export default function ChatPanel({ number = "03", showHeader = true, embedded = false }: ChatPanelProps) {
  const { messages, send, isChatLoading, scrollRef } = useChat();
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleSend = () => {
    if (!text.trim() || isChatLoading) return;
    send(text);
    setText("");
    inputRef.current?.focus();
  };

  return (
    <section
      // `flex-1` so the panel fills the height its parent bounds, rather than sizing to the
      // transcript. `minHeight: 0` is what actually lets it shrink below its content — a
      // flex item defaults to `min-height: auto`, which refuses to shrink past its children
      // and is the usual reason a nested `overflow-y-auto` silently never scrolls.
      className={`flex flex-1 flex-col ${embedded ? "" : "hud-panel hud-corners"}`}
      style={{ minHeight: 0 }}
    >
      {!embedded && <span className="hud-c-bl" />}
      {!embedded && <span className="hud-c-br" />}

      {showHeader && (
        <PanelHeader
          number={number}
          title="DENTALVISION AI CHAT"
          subtitle="CONVERSATIONAL MODULE"
          right={
            <span className="flex items-center gap-1.5 text-[13px] tracking-[0.2em] text-[#8A8A8A] mono">
              <span className="h-1.5 w-1.5 bg-[#D6D6D6] glow-dot" />
              LIVE
            </span>
          }
        />
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto bg-[#070708] p-3 md:space-y-4 md:p-4"
        style={{ minHeight: 0 }}
      >
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}

        {isChatLoading && <TypingIndicator />}
      </div>

      {/* Input */}
      <div className="border-t border-[#1a1a1a] bg-[#0a0a0a] p-2 md:p-3">
        <div className="flex items-center gap-2 border border-[#2A2A2A] bg-[#080808] px-2 py-1.5 md:gap-3 md:px-3 md:py-2">
          <button
            type="button"
            className="flex h-7 w-7 shrink-0 items-center justify-center text-[#707070] hover:text-[#D6D6D6]"
            aria-label="Attach file"
            onClick={() => alert("Attach functionality: select an image to send to the AI for analysis.")}
          >
            <Paperclip className="h-3.5 w-3.5" />
          </button>

          <span className="hidden h-5 w-px bg-[#2A2A2A] sm:block" />

          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type your message..."
            className="flex-1 bg-transparent text-[16px] tracking-[0.1em] text-[#E5E5E5] outline-none placeholder:text-[#555] md:text-[17px]"
            disabled={isChatLoading}
          />

          <button
            type="button"
            className="hidden h-7 w-7 shrink-0 items-center justify-center text-[#707070] hover:text-[#D6D6D6] sm:flex"
            aria-label="Voice input"
          >
            <Mic className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={handleSend}
            disabled={!text.trim() || isChatLoading}
            className="flex shrink-0 items-center gap-1.5 border border-[#3A3A3A] bg-[#0E0E10] px-2.5 py-1.5 text-[14px] tracking-[0.22em] text-[#D6D6D6] transition hover:border-[#909090] hover:bg-[#161616] disabled:opacity-40 disabled:hover:border-[#3A3A3A] disabled:hover:bg-[#0E0E10] mono md:px-3"
          >
            {isChatLoading ? (
              <>
                <Square className="h-3 w-3" />
                <span className="hidden sm:inline">SEND</span>
              </>
            ) : (
              <>
                <span className="hidden sm:inline">SEND</span>
                <Send className="h-3 w-3" />
              </>
            )}
          </button>
        </div>
        <div className="mt-1.5 hidden items-center justify-between text-[12.5px] tracking-[0.22em] text-[#555] mono sm:flex">
          <span>ENCRYPTED CHANNEL</span>
          <span>ENTER ↵ TO SEND</span>
        </div>
      </div>
    </section>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 fade-in">
      <div className="h-7 w-7 shrink-0 border border-[#3A3A3A] bg-[#0E0E10] md:h-8 md:w-8" />
      <div className="flex max-w-[80%] flex-col">
        <div className="mb-1 text-[13px] tracking-[0.22em] text-[#707070] mono">DENTALVISION AI</div>
        <div className="flex items-center gap-1 border border-[#2A2A2A] bg-[#0a0a0a] px-3 py-2">
          <span className="typing-dot h-1.5 w-1.5 bg-[#D6D6D6]" />
          <span className="typing-dot h-1.5 w-1.5 bg-[#D6D6D6]" />
          <span className="typing-dot h-1.5 w-1.5 bg-[#D6D6D6]" />
        </div>
      </div>
    </div>
  );
}
