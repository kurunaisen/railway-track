import type { ProfileAvatarId } from "./profile-avatars";

type AvatarArtProps = {
  id: ProfileAvatarId;
  className?: string;
};

export function AvatarArt({ id, className = "avatar-art" }: AvatarArtProps) {
  switch (id) {
    case "star":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <path
            fill="currentColor"
            d="M32 8l6.5 19.9H59L40.8 39.8l6.5 19.9L32 48.7 16.7 59.7 23.2 39.8 5 27.9h20.5L32 8z"
          />
        </svg>
      );
    case "orbit":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <circle cx="32" cy="34" r="12" fill="currentColor" />
          <ellipse cx="32" cy="34" rx="22" ry="8" fill="none" stroke="currentColor" strokeWidth="2.5" />
          <circle cx="50" cy="28" r="3" fill="currentColor" />
        </svg>
      );
    case "neural":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <circle cx="32" cy="32" r="6" fill="currentColor" />
          <circle cx="16" cy="20" r="4" fill="currentColor" />
          <circle cx="48" cy="20" r="4" fill="currentColor" />
          <circle cx="14" cy="44" r="4" fill="currentColor" />
          <circle cx="50" cy="44" r="4" fill="currentColor" />
          <path d="M32 32 L16 20 M32 32 L48 20 M32 32 L14 44 M32 32 L50 44" stroke="currentColor" strokeWidth="2" />
        </svg>
      );
    case "bolt":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <path fill="currentColor" d="M36 6 18 36h14l-4 22 22-32H36l4-20z" />
        </svg>
      );
    case "prism":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <path fill="currentColor" d="M32 10 52 48H12L32 10z" opacity="0.85" />
          <path fill="currentColor" d="M32 10v38H12l20-38z" opacity="0.5" />
        </svg>
      );
    case "comet":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <circle cx="42" cy="22" r="8" fill="currentColor" />
          <path
            d="M10 50 C22 38, 30 30, 42 22"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
            fill="none"
          />
        </svg>
      );
    case "hex":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <path fill="currentColor" d="M32 10 50 20v24L32 54 14 44V20L32 10z" />
          <path fill="none" stroke="currentColor" strokeWidth="2" d="M32 22v20M22 28h20" />
        </svg>
      );
    case "wave":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <path
            d="M8 36c8-8 12-8 20 0s12 8 20 0"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M8 46c8-8 12-8 20 0s12 8 20 0"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>
      );
    case "shield":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <path fill="currentColor" d="M32 8 52 16v16c0 12-8 20-20 24-12-4-20-12-20-24V16L32 8z" />
          <path d="M32 20v18M24 29h16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      );
    case "core":
      return (
        <svg viewBox="0 0 64 64" className={className} aria-hidden>
          <circle cx="32" cy="32" r="8" fill="currentColor" />
          <ellipse cx="32" cy="32" rx="22" ry="10" fill="none" stroke="currentColor" strokeWidth="2" />
          <ellipse cx="32" cy="32" rx="10" ry="22" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
      );
    default:
      return null;
  }
}
