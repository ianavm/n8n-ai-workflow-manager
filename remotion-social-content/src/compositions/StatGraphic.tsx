import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface Stat {
  label: string;
  value: number;
  suffix: string;
}

interface StatGraphicProps {
  stats: Stat[];
  title: string;
  brandColor: string;
  brandName: string;
}

export const StatGraphic: React.FC<StatGraphicProps> = ({
  stats,
  title,
  brandColor,
  brandName,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Title animation
  const titleSpring = spring({ frame, fps, config: { damping: 12 } });

  // Each stat gets staggered entry
  const statDelay = 2 * fps; // 2s after start
  const statSpacing = 1.5 * fps; // 1.5s between each stat

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, #0a0a0a 0%, #111122 100%)`,
        fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
      }}
    >
      {/* Background grid pattern */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
        }}
      />

      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: "12%",
          left: 60,
          right: 60,
          opacity: titleSpring,
          transform: `translateY(${(1 - titleSpring) * 20}px)`,
        }}
      >
        <div
          style={{
            fontSize: 52,
            fontWeight: 800,
            color: "#fff",
            lineHeight: 1.2,
          }}
        >
          {title}
        </div>
        <div
          style={{
            width: 80,
            height: 4,
            backgroundColor: brandColor,
            marginTop: 24,
            borderRadius: 2,
          }}
        />
      </div>

      {/* Stats */}
      {stats.map((stat, i) => {
        const entryFrame = statDelay + i * statSpacing;
        const statSpring = spring({
          frame: Math.max(0, frame - entryFrame),
          fps,
          config: { damping: 12 },
        });

        // Animated counter
        const counterValue = interpolate(
          frame,
          [entryFrame, entryFrame + 1.5 * fps],
          [0, stat.value],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        // Bar width (relative to max stat value)
        const maxVal = Math.max(...stats.map((s) => s.value));
        const barPct = (stat.value / maxVal) * 100;
        const barWidth = interpolate(
          frame,
          [entryFrame + 10, entryFrame + fps],
          [0, barPct],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        const topOffset = 38 + i * 18; // percentage

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: `${topOffset}%`,
              left: 60,
              right: 60,
              opacity: statSpring,
              transform: `translateX(${(1 - statSpring) * 40}px)`,
            }}
          >
            {/* Label */}
            <div
              style={{
                fontSize: 28,
                color: "rgba(255,255,255,0.6)",
                marginBottom: 12,
                fontWeight: 500,
              }}
            >
              {stat.label}
            </div>

            {/* Number */}
            <div
              style={{
                fontSize: 96,
                fontWeight: 900,
                color: "#fff",
                lineHeight: 1,
                marginBottom: 12,
              }}
            >
              {Math.round(counterValue)}
              <span style={{ color: brandColor, fontSize: 64 }}>
                {stat.suffix}
              </span>
            </div>

            {/* Bar */}
            <div
              style={{
                width: "100%",
                height: 8,
                backgroundColor: "rgba(255,255,255,0.1)",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${barWidth}%`,
                  height: "100%",
                  backgroundColor: brandColor,
                  borderRadius: 4,
                }}
              />
            </div>
          </div>
        );
      })}

      {/* Brand footer */}
      <div
        style={{
          position: "absolute",
          bottom: 60,
          left: 0,
          right: 0,
          textAlign: "center",
          fontSize: 24,
          color: "rgba(255,255,255,0.3)",
          fontWeight: 600,
          letterSpacing: 3,
        }}
      >
        {brandName.toUpperCase()}
      </div>
    </AbsoluteFill>
  );
};
