/**
 * Brand marks.
 *
 * Inline SVG using `currentColor` - never a raster, never a hardcoded hex.
 * That is what lets one asset sit correctly on glass in both light and dark
 * themes, and render crisply at 24px in the mobile bar (plan.md 3.0).
 *
 * The wordmark below is a deliberate typographic placeholder, not a leftover:
 * a real logo drops into the same fixed 160x32 / 32x32 boxes with no layout
 * change. Until then this is a legitimate, consistent mark.
 */

import { brand } from './brand.config';

type MarkProps = {
  /** Rendered size in px. The mark is square. */
  size?: number;
  className?: string;
};

/**
 * Mark only - mobile bar, favicon source, avatar fallback.
 * An aperture-like form: two offset rounded squares reading as layered glass.
 */
export function LogoMark({ size = 32, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="presentation"
      aria-hidden="true"
      className={className}
    >
      <rect
        x="4.5"
        y="4.5"
        width="17"
        height="17"
        rx="5.5"
        stroke="currentColor"
        strokeWidth="2"
        opacity="0.45"
      />
      <rect
        x="10.5"
        y="10.5"
        width="17"
        height="17"
        rx="5.5"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}

type LogoProps = {
  className?: string;
  /** Hide the wordmark and render only the mark. */
  markOnly?: boolean;
};

/**
 * Full lockup - desktop nav and footer.
 * Occupies the reserved 160x32 slot; a replacement must fit the same box.
 */
export function Logo({ className, markOnly = false }: LogoProps) {
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        height: 32,
        maxWidth: 160,
        color: 'var(--text)',
      }}
    >
      <LogoMark size={26} />
      {!markOnly && (
        <span
          style={{
            fontWeight: 600,
            fontSize: '1.0625rem',
            letterSpacing: '-0.02em',
            whiteSpace: 'nowrap',
          }}
        >
          {brand.name}
        </span>
      )}
    </span>
  );
}

/** Text-only wordmark, for places that already show the mark. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={className} style={{ fontWeight: 600, letterSpacing: '-0.02em' }}>
      {brand.name}
    </span>
  );
}
