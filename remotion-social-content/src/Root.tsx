import { Composition } from "remotion";
import { TextOnScreen } from "./compositions/TextOnScreen";
import { QuoteCard } from "./compositions/QuoteCard";
import { StatGraphic } from "./compositions/StatGraphic";
import { TalkingHeadOverlay } from "./compositions/TalkingHeadOverlay";

// Shared dimensions: 9:16 portrait (Reels/Shorts)
const WIDTH = 1080;
const HEIGHT = 1920;
const FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="TextOnScreen"
        component={TextOnScreen}
        durationInFrames={30 * FPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          title: "Stop wasting hours on manual marketing tasks",
          script: [
            "AI workflow automation handles your follow-ups 24/7.",
            "Smart lead scoring tells you who is ready to buy.",
            "Automated reporting saves 10+ hours per week.",
          ],
          cta: "Follow for more automation tips",
          brandColor: "#FF6D5A",
          brandName: "AnyVision Media",
        }}
      />
      <Composition
        id="QuoteCard"
        component={QuoteCard}
        durationInFrames={12 * FPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          quote: "The agencies that will thrive in 2026 are the ones automating today.",
          attribution: "Ian Immelman, AnyVision Media",
          brandColor: "#FF6D5A",
          brandName: "AnyVision Media",
        }}
      />
      <Composition
        id="StatGraphic"
        component={StatGraphic}
        durationInFrames={20 * FPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          stats: [
            { label: "Hours Saved Weekly", value: 40, suffix: "+" },
            { label: "Lead Response Time", value: 2, suffix: "min" },
            { label: "Client Retention", value: 94, suffix: "%" },
          ],
          title: "What AI Automation Did for Our Agency",
          brandColor: "#FF6D5A",
          brandName: "AnyVision Media",
        }}
      />
      <Composition
        id="TalkingHeadOverlay"
        component={TalkingHeadOverlay}
        durationInFrames={30 * FPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          bullets: [
            "Automate your client follow-ups",
            "Score leads with AI in real time",
            "Generate reports automatically",
          ],
          lowerThird: {
            name: "Ian Immelman",
            title: "Founder, AnyVision Media",
          },
          brandColor: "#FF6D5A",
        }}
      />
    </>
  );
};
