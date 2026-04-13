import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface TextOnScreenProps {
  title: string;
  script: string[];
  cta: string;
  brandColor: string;
  brandName: string;
}

export const TextOnScreen: React.FC<TextOnScreenProps> = ({
  title,
  script,
  cta,
  brandColor,
  brandName,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Timing: hook (0-3s), body lines, CTA (last 4s)
  const hookEnd = 3 * fps;
  const ctaStart = durationInFrames - 4 * fps;
  const bodyDuration = ctaStart - hookEnd;
  const lineTime = bodyDuration / Math.max(script.length, 1);

  // Hook animation
  const hookOpacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });
  const hookScale = spring({ frame, fps, config: { damping: 12 } });
  const hookExit = interpolate(
    frame,
    [hookEnd - 10, hookEnd],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // CTA animation
  const ctaProgress = spring({
    frame: Math.max(0, frame - ctaStart),
    fps,
    config: { damping: 10 },
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(160deg, #0a0a0a 0%, #1a1a2e 50%, ${brandColor}22 100%)`,
        fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
      }}
    >
      {/* Brand watermark */}
      <div
        style={{
          position: "absolute",
          top: 60,
          left: 60,
          fontSize: 28,
          color: "rgba(255,255,255,0.4)",
          fontWeight: 600,
          letterSpacing: 2,
        }}
      >
        {brandName.toUpperCase()}
      </div>

      {/* Accent line */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: interpolate(frame, [0, 30], [0, 1080], {
            extrapolateRight: "clamp",
          }),
          height: 4,
          backgroundColor: brandColor,
        }}
      />

      {/* Hook */}
      {frame < hookEnd && (
        <div
          style={{
            position: "absolute",
            top: "35%",
            left: 60,
            right: 60,
            opacity: hookOpacity * hookExit,
            transform: `scale(${hookScale})`,
          }}
        >
          <div
            style={{
              fontSize: 72,
              fontWeight: 800,
              color: "#fff",
              lineHeight: 1.1,
              textShadow: "0 4px 30px rgba(0,0,0,0.5)",
            }}
          >
            {title}
          </div>
        </div>
      )}

      {/* Body lines */}
      {script.map((line, i) => {
        const lineStart = hookEnd + i * lineTime;
        const lineEnd = hookEnd + (i + 1) * lineTime;
        const lineVisible = frame >= lineStart && frame < ctaStart;

        const lineSpring = spring({
          frame: Math.max(0, frame - lineStart),
          fps,
          config: { damping: 14 },
        });

        const lineExit = interpolate(
          frame,
          [lineEnd - 8, lineEnd],
          [1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        if (!lineVisible) return null;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: "30%",
              left: 60,
              right: 60,
              opacity: lineSpring * (frame < lineEnd - 8 ? 1 : lineExit),
              transform: `translateY(${(1 - lineSpring) * 40}px)`,
            }}
          >
            <div
              style={{
                fontSize: 28,
                color: brandColor,
                fontWeight: 700,
                marginBottom: 16,
                letterSpacing: 3,
              }}
            >
              {String(i + 1).padStart(2, "0")}
            </div>
            <div
              style={{
                fontSize: 56,
                fontWeight: 700,
                color: "#fff",
                lineHeight: 1.2,
              }}
            >
              {line}
            </div>
          </div>
        );
      })}

      {/* CTA */}
      {frame >= ctaStart && (
        <div
          style={{
            position: "absolute",
            bottom: "20%",
            left: 60,
            right: 60,
            opacity: ctaProgress,
            transform: `translateY(${(1 - ctaProgress) * 30}px)`,
          }}
        >
          <div
            style={{
              backgroundColor: brandColor,
              padding: "32px 48px",
              borderRadius: 20,
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontSize: 44,
                fontWeight: 700,
                color: "#fff",
              }}
            >
              {cta}
            </div>
          </div>
          <div
            style={{
              textAlign: "center",
              marginTop: 24,
              fontSize: 24,
              color: "rgba(255,255,255,0.5)",
            }}
          >
            {brandName}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
