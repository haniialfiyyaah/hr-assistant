import { cn } from "@/lib/utils";

const SIZES = {
  sm: "size-7",
  md: "size-8",
  lg: "size-11 sm:size-12",
} as const;

/**
 * Product mark for shell, login, and chat.
 * Inline SVG (no /public or Image optimizer) so it cannot 404 on Vercel.
 */
export function BrandMark({
  size = "sm",
  className,
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-teal-800 text-white shadow-sm",
        SIZES[size],
        className,
      )}
      aria-hidden
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className={cn(
          size === "lg" ? "size-6" : size === "md" ? "size-4" : "size-3.5",
        )}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Back sheet */}
        <path
          d="M8 5.5h7.2a1.8 1.8 0 0 1 1.8 1.8v9.4a1.8 1.8 0 0 1-1.8 1.8H8"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.55"
        />
        {/* Front sheet */}
        <path
          d="M6.2 4h7.5c.9 0 1.6.7 1.6 1.6v11.3c0 .9-.7 1.6-1.6 1.6H6.2c-.9 0-1.6-.7-1.6-1.6V5.6c0-.9.7-1.6 1.6-1.6Z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        {/* Note lines */}
        <path
          d="M8 9h5.2M8 12h5.2M8 15h3.4"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
