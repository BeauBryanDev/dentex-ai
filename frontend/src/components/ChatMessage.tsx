import type { ChatMessage as ChatMessageType } from "../types";
import { ToothAvatar, UserAvatar } from "./Avatars";
import DentalOfficeLinks from "./DentalOfficeLinks";
import Markdown from "./Markdown";

interface ChatMessageProps {
  message: ChatMessageType;
}

function dentalOfficesFromToolCalls(message: ChatMessageType) {
  const offices = (message.toolCalls ?? []).flatMap((call) => call.dental_offices ?? []);
  const resolvedLocation =
    (message.toolCalls ?? []).find((call) => call.resolved_location)?.resolved_location ??
    null;
  return { offices, resolvedLocation };
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const { offices, resolvedLocation } = dentalOfficesFromToolCalls(message);

  if (isSystem) {
    // Errors are styled apart from ordinary notices and never rendered as an assistant
    // bubble. A failed request that looks like a reply is the single most misleading thing
    // this UI could do — the previous build answered from canned mock text on any failure.
    const err = message.isError;
    return (
      <div className="flex justify-center">
        <div
          className={`border px-3 py-1 text-[13px] tracking-[0.22em] mono ${
            err
              ? "border-[#E63946]/50 bg-[#180a0b] text-[#E63946]"
              : "border-[#2A2A2A] bg-[#0a0a0a] text-[#707070]"
          }`}
        >
          {err ? "SYSTEM ALERT — " : ""}
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-start gap-2 fade-in md:gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && <ToothAvatar className="h-7 w-7 shrink-0 md:h-8 md:w-8" />}

      <div className={`flex max-w-[88%] flex-col ${isUser ? "items-end" : "items-start"} md:max-w-[80%]`}>
        <div className="mb-1 flex items-center gap-2 text-[13px] tracking-[0.22em] text-[#707070] mono">
          <span>{isUser ? "YOU" : "DENTALVISION AI"}</span>
          <span className="h-px w-3 bg-[#2A2A2A]" />
          <span>{message.timestamp}</span>
        </div>

        <div
          className={`relative border bg-[#0a0a0a] px-3 py-2 md:px-4 md:py-2.5 ${
            isUser
              ? "border-[#3A3A3A] bg-[#0E0E10]"
              : "border-[#2A2A2A] bg-[#0B0B0D]"
          }`}
        >
          {/* HUD corner brackets */}
          <span className="absolute -left-px -top-px h-2 w-2 border-l border-t border-[#909090]" />
          <span className="absolute -right-px -top-px h-2 w-2 border-r border-t border-[#909090]" />
          <span className="absolute -bottom-px -left-px h-2 w-2 border-b border-l border-[#909090]" />
          <span className="absolute -bottom-px -right-px h-2 w-2 border-b border-r border-[#909090]" />

          {isUser ? (
            <p className="whitespace-pre-wrap text-[16.5px] leading-relaxed text-[#E5E5E5] md:text-[17px]">
              {message.text}
            </p>
          ) : (
            <>
              <Markdown>{message.text}</Markdown>
              <DentalOfficeLinks offices={offices} resolvedLocation={resolvedLocation} />
            </>
          )}

          {/* An answer given with no X-ray attached is general dental knowledge, not a
              reading of this patient. Say so rather than letting it pass as a finding. */}
          {!isUser && message.groundedInAnalysis === false && (
            <div className="mt-2 border-t border-[#1a1a1a] pt-1.5 text-[13px] tracking-[0.18em] text-[#707070] mono">
              GENERAL KNOWLEDGE — NO X-RAY ATTACHED
            </div>
          )}
        </div>
      </div>

      {isUser && <UserAvatar className="h-7 w-7 shrink-0 md:h-8 md:w-8" />}
    </div>
  );
}
