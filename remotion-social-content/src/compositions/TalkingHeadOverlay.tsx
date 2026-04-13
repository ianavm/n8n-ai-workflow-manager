import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface LowerThird {
  name: string;
  title: string;
}

interface TalkingHeadOverlayProps {
  bullets: string[];
  lowerThird: LowerThird;
  brandColor: string;
}

export const TalkingHeadOverlay: React.FC<TalkingHeadOverlayProps> = ({
  bullets,
  lowerThird,
  brandColor,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Lower third appears at 1s, exits at last 2s
  const ltEntry = spring({
    frame: Math.max(0, frame - fps),
    fps,
    config: { damping: 14 },
  });
  const ltExit = interpolate(
    frame,
    [durationInFrames - 2 * fps, durationInFrames - fps],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const ltOpacity = ltEntry * ltExit;

  // Bullets appear staggered starting at 3s
  const bulletStart = 3 * fps;
  const bulletSpacing = 2.5 * fps;

  return (
    <AbsoluteFill>
      {/* Transparent background — this overlays on top of video */}

      {/* Top gradient for text readability */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "30%",
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.6) 0%, transparent 100%)",
        }}
      />

      {/* Bottom gradient for lower third */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "40%",
          background:
            "linear-gradient(0deg, rgba(0,0,0,0.8) 0%, transparent 100%)",
        }}
      />

      {/* Animated bullets (top-right area) */}
      {bullets.map((bullet, i) => {
        const entryFrame = bulletStart + i * bulletSpacing;
        const exitFrame = entryFrame + bulletSpacing;

        const bulletSpring = spring({
          frame: Math.max(0, frame - entryFrame),
          fps,
          config: { damping: 12 },
        });

        const bulletExit = interpolate(
          frame,
          [exitFrame - 10, exitFrame],
          [1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        const isVisible = frame >= entryFrame && frame < exitFrame + 10;
        if (!isVisible) return null;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: 120,
              right: 40,
              left: 40,
              opacity: bulletSpring * (frame < exitFrame - 10 ? 1 : bulletExit),
              transform: `translateX(${(1 - bulletSpring) * 30}px)`,
            }}
          >
            <div
              style={{
                backgroundColor: "rgba(0,0,0,0.7)",
                backdropFilter: "blur(10px)",
                padding: "24px 32px",
                borderRadius: 16,
                borderLeft: `4px solid ${brandColor}`,
              }}
            >
              <div
                style={{
                  fontSize: 40,
                  fontWeight: 600,
                  color: "#fff",
                  fontFamily: "'Inter', sans-serif",
                  lineHeight: 1.3,
                }}
              >
                {bullet}
              </div>
            </div>
          </div>
        );
      })}

      {/* Lower third */}
      <div
        style={{
          position: "absolute",
          bottom: 180,
          left: 40,
          opacity: ltOpacity,
          transform: `translateX(${(1 - ltEntry) * -40}px)`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
          }}
        >
          {/* Brand accent bar */}
          <div
            style={{
              width: 6,
              backgroundColor: brandColor,
              borderRadius: 3,
              marginRight: 16,
            }}
          />

          <div>
            {/* Name */}
            <div
              style={{
                fontSize: 36,
                fontWeight: 700,
                color: "#fff",
                fontFamily: "'Inter', sans-serif",
              }}
            >
              {lowerThird.name}
            </div>
            {/* Title */}
            <div
              style={{
                fontSize: 26,
                fontWeight: 400,
                color: "rgba(255,255,255,0.7)",
                fontFamily: "'Inter', sans-serif",
                marginTop: 4,
              }}
            >
              {lowerThird.title}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
