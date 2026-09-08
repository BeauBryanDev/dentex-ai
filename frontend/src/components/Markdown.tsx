import ReactMarkdown from "react-markdown";

// Claude replies in markdown, so rendering it raw showed literal `**bold**` and `-` bullets
// in the transcript. This maps each element onto the HUD's own type scale instead of pulling
// in a typography plugin, so a clinical answer reads as a formatted document without
// breaking out of the console look.


export default function Markdown({ children }: { children: string }) {
  return (
    <div className="text-[16.5px] leading-relaxed text-[#E5E5E5] md:text-[17px]">
      <ReactMarkdown
        components={{
          // Paragraph spacing is applied between siblings only, so a single-paragraph
          // reply — most of them — keeps the bubble tight to the text.
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,

          strong: ({ children }) => (
            <strong className="font-semibold text-[#F0F0F0]">{children}</strong>
          ),
          em: ({ children }) => <em className="italic text-[#D6D6D6]">{children}</em>,

          ul: ({ children }) => <ul className="mb-2 space-y-1 last:mb-0">{children}</ul>,
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
          ),
          // Square markers rather than round bullets — the HUD has no curves anywhere else.
          li: ({ children }) => (
            <li className="marker:text-[#707070]">
              <span className="flex items-start gap-2">
                <span className="mt-[0.55em] h-1 w-1 shrink-0 bg-[#909090]" />
                <span className="flex-1">{children}</span>
              </span>
            </li>
          ),

          // Headings inside a chat bubble should be labels, not banners: the bubble is
          // already the visual container, so these are sized as section markers.
          h1: ({ children }) => <Heading>{children}</Heading>,
          h2: ({ children }) => <Heading>{children}</Heading>,
          h3: ({ children }) => <Heading>{children}</Heading>,
          h4: ({ children }) => <Heading>{children}</Heading>,

          code: ({ children }) => (
            <code className="mono border border-[#2A2A2A] bg-[#0E0E10] px-1 py-px text-[15px] text-[#D6D6D6]">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="mono mb-2 overflow-x-auto border border-[#2A2A2A] bg-[#080808] p-2 text-[15px] text-[#D6D6D6] last:mb-0">
              {children}
            </pre>
          ),

          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-l-2 border-[#3A3A3A] pl-3 text-[#A5A5A5] last:mb-0">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-2 border-[#1a1a1a]" />,

          // Citations from the dental corpus can arrive as links. Opened in a new tab with
          // noreferrer so a cited source can never navigate the consultation away.
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#7FB3D5] underline underline-offset-2 hover:text-[#A9CCE3]"
            >
              {children}
            </a>
          ),

          // Tables scroll inside their own container: a wide comparison table must not make
          // the whole chat column scroll sideways.
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-[15px]">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-[#1f1f1f] bg-[#0E0E10] px-2 py-1 text-left text-[14px] tracking-[0.12em] text-[#8A8A8A] mono">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-[#1f1f1f] px-2 py-1 align-top">{children}</td>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function Heading({ children }: { children?: React.ReactNode }) {
  return (
    <div className="mb-1 mt-2 text-[14px] font-semibold tracking-[0.18em] text-[#D6D6D6] mono first:mt-0">
      {children}
    </div>
  );
}
