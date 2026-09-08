import { Cpu, Image as ImageIcon, Activity, Lock, Shield, Clock } from "lucide-react";

const footerItems = [
  { label: "AI ENGINE", value: "v7.4", icon: Cpu },
  { label: "IMAGE PROCESSOR", value: "v3.2", icon: ImageIcon },
  { label: "DIAGNOSIS MODULE", value: "v5.1", icon: Activity },
  { label: "DATA ENCRYPTION", value: "AES-256", icon: Lock },
];

export default function Footer() {
  return (
    <footer className="relative z-20 border-t border-[#1a1a1a] bg-[#070707]/95 backdrop-blur-sm">
      <div className="flex flex-col md:flex-row md:items-stretch">
        {/* OS identifier */}
        <div className="flex flex-col justify-center border-r border-[#1a1a1a] px-4 py-3 md:px-5">
          <span className="text-[14px] font-bold tracking-[0.22em] text-[#E5E5E5]">DENTALVISION OS</span>
          <span className="mt-1 text-[11px] tracking-[0.22em] text-[#8A8A8A] mono">
            NEURAL MODULES ACTIVE
          </span>
        </div>

        {/* System modules */}
        <div className="flex flex-1 items-center justify-between overflow-x-auto no-scrollbar">
          {footerItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="flex shrink-0 items-center gap-2 border-r border-[#141414] px-3 py-3 md:px-4"
              >
                <Icon className="h-3.5 w-3.5 text-[#909090]" />
                <div className="flex flex-col leading-none">
                  <span className="text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">{item.label}</span>
                  <span className="mt-1 text-[12px] tracking-[0.15em] text-[#D6D6D6] mono">{item.value}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* System status */}
        <div className="flex items-center gap-3 border-l border-[#1a1a1a] px-4 py-3 md:px-5">
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-[#909090]" />
            <div className="flex flex-col leading-none">
              <span className="text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">SYSTEM UPTIME</span>
              <span className="mt-1 text-[12px] tracking-[0.15em] text-[#D6D6D6] mono">07:42:31</span>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-[#909090]" />
            <div className="flex flex-col leading-none">
              <span className="text-[11px] tracking-[0.2em] text-[#8A8A8A] mono">SECURE LINK</span>
              <span className="mt-1 text-[12px] tracking-[0.15em] text-[#D6D6D6] mono">SSL/TLS 1.3</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom technical strip */}
      <div className="hidden md:flex h-5 items-center justify-between border-t border-[#141414] bg-[#050505] px-4 mono text-[10.5px] tracking-[0.25em] text-[#555]">
        <div className="flex items-center gap-3">
          <span>RAG SYSTEM: ONLINE</span>
          <span>•</span>
          <span>DIAGNOSTICS: READY</span>
          <span>•</span>
          <span>VISION MODULE: ARMED</span>
        </div>
        <div>© DENTALVISION / CYBERDECK INTERFACE</div>
      </div>
    </footer>
  );
}
