/** Joins class names, dropping falsy values. Small enough not to need clsx. */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}
