"use client";

import { useEffect, useState, useMemo } from "react";
import { ArrowRight, Sparkles, Calendar } from "lucide-react";
import { Button } from "@/components/ui/Button";

const CONFETTI_COLORS = ["#6C63FF", "#00D4AA", "#FF6D5A", "#3B82F6", "#F59E0B"];

interface StepActivateProps {
  loading: boolean;
  onActivate: () => void;
}

export default function StepActivate({ loading, onActivate }: StepActivateProps) {
  const [showConfetti, setShowConfetti] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowConfetti(true), 200);
    return () => clearTimeout(timer);
  }, []);

  // Stable confetti positions (deterministic, no hydration mismatch)
  const confettiItems = useMemo(
    () =>
      Array.from({ length: 20 }, (_, i) => ({
        left: `${10 + ((i * 37 + 13) % 80)}%`,
        top: `${((i * 23 + 7) % 60)}%`,
        delay: `${(i * 0.025) % 0.5}s`,
        duration: `${0.6 + ((i * 0.04) % 0.8)}s`,
        color: CONFETTI_COLORS[i % 5],
      })),
    []
  );

  return (
    <div className="text-center space-y-6 py-4">
      {/* Confetti burst */}
      {showConfetti && (
        <div className="relative h-16 overflow-hidden">
          {confettiItems.map((item, i) => (
            <div
              key={i}
              className="absolute w-2 h-2 rounded-full animate-bounce"
              style={{
                left: item.left,
                top: item.top,
                background: item.color,
                opacity: 0.8,
                animationDelay: item.delay,
                animationDuration: item.duration,
              }}
            />
          ))}
        </div>
      )}

      {/* Success icon */}
      <div className="w-20 h-20 rounded-2xl mx-auto flex items-center justify-center"
        style={{
          background: "linear-gradient(135deg, rgba(108,99,255,0.15), rgba(0,212,170,0.15))",
          border: "1px solid rgba(108,99,255,0.25)",
        }}
      >
        <Sparkles size={36} className="text-[#00D4AA]" />
      </div>

      {/* Heading */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">
          You&apos;re all set!
        </h2>
        <p className="text-sm text-[#8B95A9] max-w-sm mx-auto leading-relaxed">
          Your portal is ready. Explore your dashboard, connect your tools, and
          start automating your business.
        </p>
      </div>

      {/* What's next cards */}
      <div className="space-y-2 max-w-sm mx-auto">
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/[0.08] bg-white/[0.03] text-left">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#6C63FF]/10 border border-[#6C63FF]/20">
            <span className="text-sm">1</span>
          </div>
          <span className="text-sm text-[#B0B8C8]">
            Explore your dashboard and review your KPIs
          </span>
        </div>
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/[0.08] bg-white/[0.03] text-left">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#00D4AA]/10 border border-[#00D4AA]/20">
            <span className="text-sm">2</span>
          </div>
          <span className="text-sm text-[#B0B8C8]">
            Connect your business tools in the Connections hub
          </span>
        </div>
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/[0.08] bg-white/[0.03] text-left">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#FF6D5A]/10 border border-[#FF6D5A]/20">
            <span className="text-sm">3</span>
          </div>
          <span className="text-sm text-[#B0B8C8]">
            Watch your first automation run and save you time
          </span>
        </div>
      </div>

      {/* CTAs */}
      <div className="space-y-3 pt-2 max-w-sm mx-auto">
        <Button
          variant="coral"
          size="lg"
          className="w-full"
          loading={loading}
          onClick={onActivate}
        >
          Go to Dashboard
          <ArrowRight size={16} className="ml-1" />
        </Button>

        <a
          href="https://calendly.com/anyvisionmedia/onboarding"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors py-2"
        >
          <Calendar size={14} />
          Book a free onboarding call
        </a>
      </div>

      {/* Trial reminder */}
      <p className="text-xs text-[#4B5563]">
        You have 30 days to explore everything. No credit card needed.
      </p>
    </div>
  );
}
