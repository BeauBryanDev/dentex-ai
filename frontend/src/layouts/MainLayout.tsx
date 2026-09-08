import { useState } from "react";
import { Upload, MessageSquare, BarChart3 } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import UploadPanel from "../components/UploadPanel";
import TeethTable from "../components/TeethTable";
import ChatPanel from "../components/ChatPanel";
import AnalysisImage from "../components/AnalysisImage";
import Dashboard from "../components/Dashboard";

type MobileView = "UPLOAD" | "CHAT" | "ANALYSIS";

export default function MainLayout() {
  const [activeView, setActiveView] = useState<MobileView>("UPLOAD");
  const [activeNav, setActiveNav] = useState("DASHBOARD");

  return (
    <div className="flex min-h-screen flex-col">
      <Header activeView={activeNav} onNavigate={setActiveNav} />

      <main className="mx-2 flex-1 px-2 py-2 md:px-3 md:py-3 lg:px-4">
        {/* Desktop / tablet layout: 3 columns */}
        <div className="hidden gap-3 md:grid md:grid-cols-2 lg:grid-cols-[25%_40%_35%]">
          {/* Left column */}
          <div className="flex flex-col gap-3">
            <UploadPanel number="01" />
            <TeethTable number="02" />
          </div>

          {/* Center column.
             *  The chat panel is sticky on desktop, but scrolls with the page on mobile. */}
          <div className="flex h-[calc(100vh-8.5rem)] min-h-[420px] flex-col lg:sticky lg:top-3 lg:self-start">
            <ChatPanel number="03" />
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-3">
            <AnalysisImage />
            <Dashboard />
          </div>
        </div>

        {/* Mobile single-view layout with bottom nav */}
        <div className="md:hidden">
          {activeView === "UPLOAD" && (
            <div className="flex flex-col gap-3 pb-24 fade-in">
              <UploadPanel number="01" />
              <TeethTable number="02" scrollMaxHeight="max-h-[400px]" />
            </div>
          )}
          {activeView === "CHAT" && (
            <div className="flex h-[calc(100vh-180px)] flex-col pb-24 fade-in">
              <ChatPanel number="03" />
            </div>
          )}
          {activeView === "ANALYSIS" && (
            <div className="flex flex-col gap-3 pb-24 fade-in">
              <AnalysisImage />
              <Dashboard />
            </div>
          )}
        </div>
      </main>

      <Footer />

      {/* Mobile bottom navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-[#1a1a1a] bg-[#080808]/95 backdrop-blur-md md:hidden">
        <div className="grid grid-cols-3">
          <NavButton
            label="UPLOAD"
            icon={Upload}
            active={activeView === "UPLOAD"}
            onClick={() => setActiveView("UPLOAD")}
          />
          <NavButton
            label="CHAT"
            icon={MessageSquare}
            active={activeView === "CHAT"}
            onClick={() => setActiveView("CHAT")}
          />
          <NavButton
            label="ANALYSIS"
            icon={BarChart3}
            active={activeView === "ANALYSIS"}
            onClick={() => setActiveView("ANALYSIS")}
          />
        </div>
      </nav>
    </div>
  );
}

function NavButton({
  label,
  icon: Icon,
  active,
  onClick,
}: {
  label: string;
  icon: any;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`relative flex flex-col items-center gap-1 py-2.5 transition ${
        active ? "bg-[#0E0E10] text-[#E5E5E5]" : "text-[#707070] hover:text-[#A5A5A5]"
      }`}
    >
      {active && <span className="absolute left-1/2 top-0 h-[2px] w-10 -translate-x-1/2 bg-[#D6D6D6]" />}
      <Icon className="h-4 w-4" />
      <span className="text-[11px] tracking-[0.22em] mono">{label}</span>
    </button>
  );
}
