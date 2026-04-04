interface PlatformIconProps {
  platform: string;
  size?: number;
}

const PLATFORM_CONFIG: Record<string, { label: string; color: string; letter: string }> = {
  google_ads: { label: "Google Ads", color: "#4285F4", letter: "G" },
  meta_ads: { label: "Meta Ads", color: "#0668E1", letter: "M" },
  tiktok_ads: { label: "TikTok Ads", color: "#FF0050", letter: "T" },
  linkedin_ads: { label: "LinkedIn Ads", color: "#0A66C2", letter: "L" },
  multi_platform: { label: "Multi-Platform", color: "#10B981", letter: "+" },
  facebook: { label: "Facebook", color: "#1877F2", letter: "F" },
  instagram: { label: "Instagram", color: "#E4405F", letter: "I" },
  linkedin: { label: "LinkedIn", color: "#0A66C2", letter: "L" },
  twitter: { label: "X/Twitter", color: "#1DA1F2", letter: "X" },
  tiktok: { label: "TikTok", color: "#FF0050", letter: "T" },
  youtube: { label: "YouTube", color: "#FF0000", letter: "Y" },
  threads: { label: "Threads", color: "#000000", letter: "Th" },
  bluesky: { label: "Bluesky", color: "#0085FF", letter: "B" },
  pinterest: { label: "Pinterest", color: "#E60023", letter: "P" },
};

export function PlatformIcon({ platform, size = 24 }: PlatformIconProps) {
  const config = PLATFORM_CONFIG[platform] ?? { label: platform, color: "#6B7280", letter: "?" };

  return (
    <div
      title={config.label}
      className="inline-flex items-center justify-center rounded-md font-bold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.45,
        background: `${config.color}20`,
        color: config.color,
        flexShrink: 0,
      }}
    >
      {config.letter}
    </div>
  );
}
