import Image from "next/image";

import { cn } from "@/lib/utils";

import brandMark from "../public/brand-mark.png";

const SIZES = {
  sm: "size-7",
  md: "size-8",
  lg: "size-11 sm:size-12",
} as const;

/**
 * Product mark used in shell, login, and chat — matches favicon / app icon.
 * Imported (not /public URL) so the asset ships in the Next bundle on Vercel.
 */
export function BrandMark({
  size = "sm",
  className,
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const box = SIZES[size];
  const px = size === "lg" ? 48 : size === "md" ? 32 : 28;

  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 overflow-hidden rounded-full shadow-sm",
        box,
        className,
      )}
    >
      <Image
        src={brandMark}
        alt=""
        width={px}
        height={px}
        className="size-full object-cover"
        priority={size === "lg"}
      />
    </span>
  );
}
