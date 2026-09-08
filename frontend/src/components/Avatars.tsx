import mainToothIcon from "../assets/main_tooth_icon.svg";

export function ToothAvatar({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex shrink-0 items-center justify-center border border-[#3A3A3A] bg-[#0E0E10] ${className}`}>
      <img
        src={mainToothIcon}
        alt="DentalVision AI"
        className="h-3/5 w-3/5 object-contain"
        draggable={false}
      />
      <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 bg-[#D6D6D6] glow-dot" />
    </div>
  );
}

export function UserAvatar({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex shrink-0 items-center justify-center border border-[#2A2A2A] bg-[#0E0E10] ${className}`}>
      <svg
        className="h-3/5 w-3/5 text-[#A5A5A5]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21 C4 16 8 14 12 14 C16 14 20 16 20 21" />
      </svg>
    </div>
  );
}
