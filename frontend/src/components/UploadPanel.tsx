import { useCallback, useRef, useState } from "react";
import { FileWarning, CheckCircle2, X } from "lucide-react";
import { useAppStore } from "../stores/appStore";
import { useAnalysis } from "../hooks/useAnalysis";

interface UploadPanelProps {
  number?: string;
  compact?: boolean;
}

export default function UploadPanel({ number = "01", compact = false }: UploadPanelProps) {
  const { uploadedImage, setUploadedImage } = useAppStore();
  const { handleUpload, isAnalyzing, errorMessage } = useAnalysis();


  
  // Kept so TRY AGAIN can resend the same bytes. Upload and analysis are a single request
  // now, so a retry needs the File itself — there is no server-side upload id to re-poke.
  const lastFileRef = useRef<File | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<"" | "UPLOADING" | "ANALYZING" | "">("");

  const onFile = useCallback(
    (file: File) => {
      if (!file) return;
      const validTypes = ["image/jpeg", "image/png", "image/jpg", "application/dicom"];
      if (!validTypes.includes(file.type) && !file.name.toLowerCase().endsWith(".dcm")) {
        useAppStore.getState().setErrorMessage("Unsupported file format. Use JPG, PNG or DICOM.");
        return;
      }
      useAppStore.getState().setErrorMessage(null);
      lastFileRef.current = file;

      // Simulate upload progress
      setPhase("UPLOADING");
      let p = 0;
      const tick = setInterval(() => {
        p += Math.random() * 18;
        if (p >= 100) {
          p = 100;
          clearInterval(tick);
          setPhase("ANALYZING");
        }
        setProgress(Math.min(100, p));
      }, 220);

      handleUpload(file).finally(() => {
        clearInterval(tick);
        setProgress(0);
        setPhase("");
      });
    },
    [handleUpload]
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  const clearImage = () => {
    setUploadedImage(null);
    useAppStore.getState().setErrorMessage(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <section className="hud-panel hud-corners flex flex-col">
      <span className="hud-c-bl" />
      <span className="hud-c-br" />
      <PanelHeader number={number} title="UPLOAD IMAGING" subtitle="INPUT MODULE" />

      <div className="px-3 py-3 md:px-4 md:py-4">
        {!uploadedImage ? (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`group relative flex cursor-pointer flex-col items-center justify-center gap-3 border border-dashed px-4 py-8 text-center transition-all md:py-10 ${
              dragOver
                ? "border-[#D6D6D6] bg-[#161616]"
                : "border-[#3A3A3A] bg-[#0a0a0a] hover:border-[#909090] hover:bg-[#101010]"
            }`}
          >
            {/* Corner brackets */}
            <CornerBrackets />

            <div className="relative">
              <div className="absolute inset-0 -m-2 border border-[#1a1a1a]" />
              <ToothGlyph className="relative h-12 w-12 text-[#A5A5A5] transition group-hover:text-[#D6D6D6] md:h-14 md:w-14" />
            </div>

            <div>
              <p className="text-[14px] font-semibold tracking-[0.22em] text-[#E5E5E5]">
                DRAG & DROP DENTAL IMAGE
              </p>
              <p className="mt-1 text-[12px] tracking-[0.22em] text-[#A5A5A5] mono">
                OR CLICK TO BROWSE
              </p>
            </div>

            <div className="flex items-center gap-2 text-[11px] tracking-[0.22em] text-[#707070] mono">
              <span>JPG</span>
              <span className="text-[#3A3A3A]">/</span>
              <span>PNG</span>
              <span className="text-[#3A3A3A]">/</span>
              <span>DCM</span>
            </div>

            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/jpg,.dcm"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
              }}
            />
          </div>
        ) : (
          <div className="relative border border-[#2A2A2A] bg-[#0a0a0a] p-2">
            <div className="relative h-44 w-full overflow-hidden border border-[#1a1a1a] md:h-52">
              <img
                src={uploadedImage.dataUrl}
                alt={uploadedImage.name}
                className="h-full w-full object-cover opacity-80"
              />
              {phase === "ANALYZING" && <div className="scan-line" />}
              <div className="absolute left-2 top-2 flex items-center gap-1.5 bg-black/60 px-2 py-0.5">
                <CheckCircle2 className="h-3 w-3 text-[#D6D6D6]" />
                <span className="text-[11px] tracking-[0.2em] text-[#D6D6D6] mono">LOADED</span>
              </div>
              <button
                onClick={clearImage}
                className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center bg-black/70 text-[#A5A5A5] hover:text-[#E5E5E5]"
                aria-label="Remove image"
              >
                <X className="h-3 w-3" />
              </button>
              {/* Corner brackets over preview */}
              <div className="pointer-events-none absolute left-1 top-1 h-2 w-2 border-l border-t border-[#909090]" />
              <div className="pointer-events-none absolute right-1 top-1 h-2 w-2 border-r border-t border-[#909090]" />
              <div className="pointer-events-none absolute bottom-1 left-1 h-2 w-2 border-b border-l border-[#909090]" />
              <div className="pointer-events-none absolute bottom-1 right-1 h-2 w-2 border-b border-r border-[#909090]" />
            </div>
            <div className="mt-2 flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-[12px] tracking-[0.18em] text-[#D6D6D6] mono truncate max-w-[200px]">
                  {uploadedImage.name}
                </span>
                <span className="mt-0.5 text-[11px] tracking-[0.2em] text-[#707070] mono">
                  {(uploadedImage.size / 1024).toFixed(1)} KB
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => inputRef.current?.click()}
                  className="border border-[#3A3A3A] bg-[#101010] px-2 py-1 text-[11px] tracking-[0.22em] text-[#A5A5A5] hover:border-[#909090] hover:text-[#E5E5E5] mono"
                >
                  REPLACE
                </button>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/jpg,.dcm"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onFile(f);
                }}
              />
            </div>
          </div>
        )}

        {/* Progress / analyzing state */}
        {(phase === "UPLOADING" || isAnalyzing || phase === "ANALYZING") && (
          <div className="mt-3 border border-[#1a1a1a] bg-[#0a0a0a] p-3 fade-in">
            <div className="flex items-center justify-between">
              <span className="text-[12px] tracking-[0.2em] text-[#D6D6D6] mono">
                {phase === "UPLOADING" ? "UPLOADING IMAGE…" : "ANALYZING IMAGE…"}
              </span>
              <span className="text-[12px] tracking-[0.2em] text-[#A5A5A5] mono">
                {phase === "UPLOADING" ? `${Math.round(progress)}%` : "AI"}
              </span>
            </div>
            <div className="mt-2 h-1.5 w-full bg-[#1a1a1a]">
              <div
                className="h-full bg-[#D6D6D6] transition-all"
                style={{ width: phase === "UPLOADING" ? `${progress}%` : "100%" }}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-1 text-[11px] tracking-[0.2em] text-[#707070] mono md:grid-cols-4">
              <span className={phase === "ANALYZING" || isAnalyzing ? "text-[#D6D6D6]" : ""}>
                • DETECTING TEETH
              </span>
              <span>• FDI MAPPING</span>
              <span>• LESION SCAN</span>
              <span>• GENERATING</span>
            </div>
          </div>
        )}

        {/* Error state */}
        {errorMessage && (
          <div className="mt-3 border border-[#E63946]/40 bg-[#1a0808] p-3 fade-in">
            <div className="flex items-start gap-2">
              <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#E63946]" />
              <div className="flex-1">
                <p className="text-[12px] tracking-[0.22em] text-[#E63946] mono">SYSTEM ALERT</p>
                <p className="mt-1 text-[13px] text-[#D6D6D6]">{errorMessage}</p>
                <button
                  onClick={() => lastFileRef.current && handleUpload(lastFileRef.current)}
                  className="mt-2 border border-[#E63946]/60 bg-transparent px-3 py-1 text-[11px] tracking-[0.22em] text-[#E63946] hover:bg-[#E63946]/10 mono"
                >
                  TRY AGAIN
                </button>
              </div>
            </div>
          </div>
        )}

        {!compact && (
          <div className="mt-3 flex items-center justify-between text-[11px] tracking-[0.22em] text-[#555] mono">
            <span>SRC: LOCAL / UPLOAD</span>
            <span>ENC: AES-256</span>
          </div>
        )}
      </div>
    </section>
  );
}

export function PanelHeader({
  number,
  title,
  subtitle,
  right,
}: {
  number?: string;
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="relative flex items-center justify-between border-b border-[#1a1a1a] bg-[#0a0a0a] px-3 py-2 md:px-4">
      <div className="flex items-center gap-2 md:gap-3">
        {number && (
          <span className="border border-[#2A2A2A] bg-[#0E0E10] px-1.5 py-0.5 text-[12px] tracking-[0.15em] text-[#909090] mono">
            {number}
          </span>
        )}
        <h3 className="text-[13px] font-semibold tracking-[0.25em] text-[#E5E5E5] md:text-[14px]">{title}</h3>
        {subtitle && (
          <span className="hidden md:inline text-[11px] tracking-[0.22em] text-[#707070] mono">
            • {subtitle}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {right}
        <span className="hidden md:flex gap-0.5">
          <span className="h-1 w-1 bg-[#909090]" />
          <span className="h-1 w-1 bg-[#909090]" />
          <span className="h-1 w-1 bg-[#909090]" />
        </span>
      </div>
    </div>
  );
}

function CornerBrackets() {
  return (
    <>
      <span className="absolute left-1 top-1 h-3 w-3 border-l border-t border-[#909090]" />
      <span className="absolute right-1 top-1 h-3 w-3 border-r border-t border-[#909090]" />
      <span className="absolute bottom-1 left-1 h-3 w-3 border-b border-l border-[#909090]" />
      <span className="absolute bottom-1 right-1 h-3 w-3 border-b border-r border-[#909090]" />
    </>
  );
}

function ToothGlyph({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 8 C16 8 12 12 12 18 C12 24 14 30 16 38 C17.5 44 18 50 20 56 C21 58.5 23 60 25 60 C27.5 60 29 58 29.5 55 L31 44 C31.4 41 32.6 41 33 44 L34.5 55 C35 58 36.5 60 39 60 C41 60 43 58.5 44 56 C46 50 46.5 44 48 38 C50 30 52 24 52 18 C52 12 48 8 42 8 C37 8 33 11 32 13 C31 11 27 8 22 8 Z" />
      <path d="M22 14 C19 14 17 17 17 20" stroke="currentColor" opacity="0.6" />
      <path d="M42 14 C45 14 47 17 47 20" stroke="currentColor" opacity="0.6" />
    </svg>
  );
}
