import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface QuoteCardProps {
  quote: string;
  attribution: string;
  brandColor: string;
  brandName: string;
}

export const QuoteCard: React.FC<QuoteCardProps> = ({
  quote,
  attribution,
  brandColor,
  brandName,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Typewriter effect for quote
  const charsToShow = Math.floor(
    interpolate(frame, [15, durationInFrames - 3 * fps], [0, quote.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );

  // Attribution fade in
  const attrStart = durationInFrames - 4 * fps;
  const attrOpacity = interpolate(
    frame,
    [attrStart, attrStart + 15],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Opening quote mark animation
  const quoteMarkSpring = spring({ frame, fps, config: { damping: 8 } });

  // Accent bar
  const barWidth = interpolate(frame, [0, 20], [0, 6], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: "#0a0a0a",
        fontFamily: "'Georgia', 'Times New Roman', serif",
      }}
    >
      {/* Subtle gradient overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 30% 40%, ${brandColor}15 0%, transparent 70%)`,
        }}
      />

      {/* Left accent bar */}
      <div
        style={{
          position: "absolute",
          left: 60,
          top: "25%",
          width: barWidth,
          height: "50%",
          backgroundColor: brandColor,
          borderRadius: 3,
        }}
      />

      {/* Opening quote mark */}
      <div
        style={{
          position: "absolute",
          top: "22%",
          left: 100,
          fontSize: 200,
          color: brandColor,
          opacity: quoteMarkSpring * 0.3,
          transform: `scale(${quoteMarkSpring})`,
          fontFamily: "Georgia, serif",
          lineHeight: 1,
        }}
      >
        {"\u201C"}
      </div>

      {/* Quote text (typewriter) */}
      <div
        style={{
          position: "absolute",
          top: "32%",
          left: 100,
          right: 80,
          paddingRight: 20,
        }}
      >
        <div
          style={{
            fontSize: 54,
            fontWeight: 400,
            color: "#fff",
            lineHeight: 1.4,
            fontStyle: "italic",
          }}
        >
          {quote.slice(0, charsToShow)}
          <span
            style={{
              opacity: frame % 20 < 10 ? 1 : 0,
              color: brandColor,
            }}
          >
            |
          </span>
        </div>
      </div>

      {/* Attribution */}
      <div
        style={{
          position: "absolute",
          bottom: "25%",
          left: 100,
          right: 80,
          opacity: attrOpacity,
        }}
      >
        <div
          style={{
            width: 60,
            height: 2,
            backgroundColor: brandColor,
            marginBottom: 20,
          }}
        />
        <div
          style={{
            fontSize: 32,
            color: "rgba(255,255,255,0.7)",
            fontFamily: "'Inter', sans-serif",
            fontStyle: "normal",
          }}
        >
          {attribution}
        </div>
      </div>

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
          fontFamily: "'Inter', sans-serif",
          letterSpacing: 3,
        }}
      >
        {brandName.toUpperCase()}
      </div>
    </AbsoluteFill>
  );
};
