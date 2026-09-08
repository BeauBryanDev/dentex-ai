import { ExternalLink, MapPin } from "lucide-react";
import type { DentalOfficeOut } from "../types";

interface DentalOfficeLinksProps {
  offices: DentalOfficeOut[];
  resolvedLocation?: string | null;
}

export default function DentalOfficeLinks({
  offices,
  resolvedLocation,
}: DentalOfficeLinksProps) {
  if (!offices.length) return null;

  return (
    <div className="mt-3 border-t border-[#1a1a1a] pt-2">
      <div className="mb-2 text-[13px] tracking-[0.18em] text-[#707070] mono">
        NEARBY DENTAL OFFICES
        {resolvedLocation ? ` — ${resolvedLocation.toUpperCase()}` : ""}
      </div>

      <ul className="space-y-2">
        {offices.map((office) => (
          <li
            key={`${office.name}-${office.address}`}
            className="border border-[#1f1f1f] bg-[#080808] px-2.5 py-2"
          >
            <div className="text-[15px] font-medium text-[#E5E5E5]">{office.name}</div>
            <div className="mt-1 flex items-start gap-1.5 text-[14px] leading-snug text-[#A5A5A5]">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#707070]" />
              <span>{office.address}</span>
            </div>

            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-[#8A8A8A] mono">
              {office.rating != null && (
                <span>{office.rating.toFixed(1)}/5</span>
              )}
              {office.user_ratings_total != null && (
                <span>{office.user_ratings_total} reviews</span>
              )}
              {office.open_now === true && <span className="text-[#7FB3D5]">OPEN NOW</span>}
              {office.open_now === false && <span>CLOSED NOW</span>}
            </div>

            {office.maps_url && (
              <a
                href={office.maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1.5 text-[13px] tracking-[0.12em] text-[#7FB3D5] underline underline-offset-2 hover:text-[#A9CCE3] mono"
              >
                OPEN IN GOOGLE MAPS
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
