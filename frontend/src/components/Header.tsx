import { useEffect, useState } from "react";
import { Activity, User } from "lucide-react";
import landToothIcon from "../assets/land_tooth_icon.svg";
// Anthropic's Claude mark — the attribution for the LLM behind the agent. Over the 4 KB
// default inline limit, which is why vite.config.ts raises `assetsInlineLimit`.
import claudeMark from "../assets/claude-mark.png";

// Backend Icons
import PythonIcon from "../assets/Python.svg";
import FastAPIIcon from "../assets/FastAPI.svg";
import OpenCVIcon from "../assets/OpenCV.svg";
import NumpyIcon from "../assets/Numpy.svg";
import YOLOIcon  from "../assets/Ultralytics.png";

// Frontend Icons
import ReactIcon from "../assets/React.svg";
import TypeScriptIcon from "../assets/TypeScript.svg";
import TailwindIcon from "../assets/Tailwind.svg";
import ViteIcon from "../assets/Vite.svg";

interface HeaderProps {
  activeView?: string;
  onNavigate?: (view: string) => void;
}


/** One acknowledged dependency: its mark, its name, and its home page. */
type Credit = { src: string; label: string; link: string };

const BACKEND_CREDITS: Credit[] = [
  { src: PythonIcon, label: "Python", link: "https://www.python.org/" },
  { src: FastAPIIcon, label: "FastAPI", link: "https://fastapi.tiangolo.com/" },
  { src: OpenCVIcon, label: "OpenCV", link: "https://opencv.org/" },
  { src: NumpyIcon, label: "Numpy", link: "https://numpy.org/" },
  { src: YOLOIcon, label: "YOLO", link: "https://ultralytics.com/" },
]

const FRONTEND_CREDITS: Credit[] = [
  { src: ReactIcon, label: "React", link: "https://reactjs.org/" },
  { src: TypeScriptIcon, label: "TypeScript", link: "https://www.typescriptlang.org/" },
  { src: TailwindIcon, label: "Tailwind", link: "https://tailwindcss.com/" },
  { src: ViteIcon, label: "Vite", link: "https://vitejs.dev/" },
]


const navItems = ["DASHBOARD"];

export default function Header({ activeView = "DASHBOARD", onNavigate }: HeaderProps) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="relative z-30 border-b border-[#1a1a1a] bg-[#080808]/95 backdrop-blur-sm">
      <div className="flex h-16 items-stretch">
        {/* Left: Logo */}
        <div className="flex items-center gap-3 border-r border-[#1a1a1a] px-4 md:px-5">
          <ToothLogo className="h-9 w-9 shrink-0" />
          <div className="hidden sm:flex flex-col leading-none">
            <span className="text-[17px] font-bold tracking-[0.18em] text-[#F0F0F0]">
              DENTEX
            </span>
            <span className="mt-1 text-[11px] tracking-[0.22em] text-[#8A8A8A] mono">
              AI DENTIST ASSISTANT AGENT
            </span>
          </div>
        </div>

        {/* Center: System status + nav (desktop) */}
        <div className="hidden lg:flex flex-1 items-center justify-between px-6">
          <div className="flex items-center gap-6 mono text-[12px] tracking-[0.2em] text-[#8A8A8A]">
            <StatusItem label="NEURAL LINK" value="ONLINE" bright />
            <StatusItem label="AI ENGINE" value="READY" />
            <StatusItem label="VISION SYS" value="READY" />
          </div>

          <TechCredits />

          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item}
                onClick={() => onNavigate?.(item)}
                className={`relative px-4 py-2 text-[13px] tracking-[0.2em] mono transition ${
                  activeView === item
                    ? "text-[#F0F0F0] bg-[#161616]"
                    : "text-[#8A8A8A] hover:text-[#D6D6D6]"
                }`}
              >
                {item}
                {activeView === item && (
                  <span className="absolute left-0 top-0 h-[2px] w-full bg-[#E5E5E5]" />
                )}
                {activeView === item && (
                  <span className="absolute left-0 bottom-0 h-[2px] w-1/3 bg-[#E5E5E5]" />
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Center: time/date (tablet) */}
        <div className="hidden md:flex lg:hidden flex-1 items-center justify-center">
          <div className="flex items-center gap-4 mono text-[12px] tracking-[0.2em] text-[#8A8A8A]">
            <StatusItem label="NEURAL" value="ONLINE" bright />
            <span className="text-[#555]">|</span>
            <PoweredByClaude />
          </div>
        </div>

        {/* Mobile: the attribution takes the spacer, since it is the one thing here
            that has to stay visible at every width. */}
        <div className="flex flex-1 items-center justify-center md:hidden">
          <PoweredByClaude compact />
        </div>

        {/* Right: user status */}
        <div className="flex items-center gap-3 border-l border-[#1a1a1a] px-3 md:px-5">
          <div className="hidden sm:flex flex-col items-end leading-none">
            <span className="text-[13px] tracking-[0.2em] text-[#D6D6D6] mono">DENTIST</span>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#D6D6D6] glow-dot" />
              <span className="text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">STATUS: ACTIVE</span>
            </div>
          </div>
          <div className="flex h-9 w-9 items-center justify-center border border-[#2A2A2A] bg-[#0E0E10]">
            <User className="h-4 w-4 text-[#D6D6D6]" />
          </div>
        </div>
      </div>

      {/* Sub status bar (desktop only) */}
      <div className="hidden lg:flex h-6 items-center justify-between border-t border-[#141414] bg-[#060606] px-6 mono text-[11px] tracking-[0.22em] text-[#707070]">
        <div className="flex items-center gap-4">
          <span>CYBERDECK v2.1.0</span>
          <span className="text-[#2A2A2A]">|</span>
          <span>BUILD 2077.05.20</span>
          <span className="text-[#2A2A2A]">|</span>
          <span>USER: ?? </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <Activity className="h-2.5 w-2.5" /> SYS UPTIME 99.97%
          </span>
          <span className="text-[#2A2A2A]">|</span>
          <span>{time.toLocaleString()}</span>
        </div>
      </div>
    </header>
  );
}

function StatusItem({ label, value, bright = false }: { label: string; value: string; bright?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-[#555]">{label}:</span>
      <span className={bright ? "text-[#D6D6D6]" : "text-[#A5A5A5]"}>{value}</span>
    </span>
  );
}

/**
 * The credit strip: thank to  these projects, and the LLM behind the agent.
 */
function TechCredits() {
  return (
    <span className="flex items-center gap-10">
      <CreditRail credits={BACKEND_CREDITS} />
      <PoweredByClaude />
      <CreditRail credits={FRONTEND_CREDITS} />
    </span>
  );
}

function CreditRail({ credits }: { credits: Credit[] }) {
  return (
    <span className="hidden xl:flex items-center gap-8">
      {credits.map(({ src, label, link }) => (
        <a
          key={label}
          href={link}
          target="_blank"
          // noopener is the security half (the opened tab cannot reach back through
          // window.opener); noreferrer keeps it working in older browsers too.
          rel="noopener noreferrer"
          title={label}
          aria-label={label}
          className="opacity-55 transition hover:opacity-100 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D6D6D6]"
        >
          <img
            src={src}
            alt={label}
            // 28px against the Claude mark's 32px: big enough to read the logos, small
            // enough that the attribution in the middle stays the largest thing here.
            className="h-7 w-7 shrink-0 object-contain"
            draggable={false}
          />
        </a>
      ))}
    </span>
  );
}

function PoweredByClaude({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5 whitespace-nowrap">
      <a
        href="https://docs.claude.com/en/docs/about-claude/models/overview"
        target="_blank"
        rel="noopener noreferrer"
        title="Claude by Anthropic — model documentation"
        aria-label="Claude by Anthropic — model documentation"
        className="shrink-0 transition hover:opacity-80 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#D6D6D6]"
      >
        <img
          src={claudeMark}
          alt="Claude by Anthropic"
          className={`shrink-0 object-contain ${compact ? "h-7 w-7" : "h-8 w-8"}`}
          draggable={false}
        />
      </a>
      <span
        className={`mono font-semibold tracking-[0.16em] text-[#9A9A9A] ${
          compact ? "text-[12px]" : "text-[14px]"
        }`}
      >
        POWERED BY{" "}
        <span className="text-[#F0F0F0]">{compact ? "CLAUDE" : "CLAUDE-SONNET-5"}</span>
      </span>
    </span>
  );
}

export function ToothLogo({ className = "" }: { className?: string }) {
  return (
    <img
      src={landToothIcon}
      alt="DentalVision"
      // The source art is pale mint (#E0F2F1) on transparent. Left as-is: it reads as the
      // one spot of warmth against the greyscale HUD, which is what a logo is for.
      className={`object-contain ${className}`}
      draggable={false}
    />
  );
}
