"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import StepBusinessProfile from "@/components/onboarding/StepBusinessProfile";
import StepConnectTools from "@/components/onboarding/StepConnectTools";
import StepChooseAutomation from "@/components/onboarding/StepChooseAutomation";
import StepPreview from "@/components/onboarding/StepPreview";
import StepActivate from "@/components/onboarding/StepActivate";
import type { StepData } from "@/components/onboarding/types";

const TOTAL_STEPS = 5;

const STEP_LABELS = [
  "Business Profile",
  "Connect Tools",
  "Choose Automation",
  "Preview",
  "Activate",
];

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [error, setError] = useState("");
  const [stepData, setStepData] = useState<StepData>({});
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [skippedSteps, setSkippedSteps] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  // Load saved progress on mount
  useEffect(() => {
    async function loadProgress() {
      try {
        const res = await fetch("/api/portal/onboarding");
        if (res.ok) {
          const data = await res.json();
          if (data.progress) {
            setCurrentStep(data.progress.current_step || 1);
            setStepData(data.progress.step_data || {});
            setCompletedSteps(data.progress.completed_steps || []);
            setSkippedSteps(data.progress.skipped_steps || []);
          }
        }
      } catch {
        // Start fresh on error
      }
      setInitialLoading(false);
    }
    loadProgress();
  }, []);

  // Persist progress to DB
  const saveProgress = useCallback(
    async (
      step: number,
      data: StepData,
      completed: number[],
      skipped: number[]
    ) => {
      try {
        await fetch("/api/portal/onboarding", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            current_step: step,
            step_data: data,
            completed_steps: completed,
            skipped_steps: skipped,
          }),
        });
      } catch {
        // Silently fail — user can continue, data saves next time
      }
    },
    []
  );

  function handleUpdateStepData(partial: Partial<StepData>) {
    const updated = { ...stepData, ...partial };
    setStepData(updated);
  }

  async function handleNext() {
    setLoading(true);

    const newCompleted = completedSteps.includes(currentStep)
      ? completedSteps
      : [...completedSteps, currentStep];
    setCompletedSteps(newCompleted);

    if (currentStep === TOTAL_STEPS) {
      // Complete onboarding
      try {
        const res = await fetch("/api/portal/onboarding/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ step_data: stepData }),
        });
        if (!res.ok) {
          setError("Something went wrong. Please try again.");
          setLoading(false);
          return;
        }
      } catch {
        setError("Network error. Please try again.");
        setLoading(false);
        return;
      }
      setLoading(false);
      router.push("/portal");
      return;
    }

    const nextStep = currentStep + 1;
    setCurrentStep(nextStep);
    await saveProgress(nextStep, stepData, newCompleted, skippedSteps);
    setLoading(false);
  }

  async function handleSkip() {
    setLoading(true);
    const newSkipped = skippedSteps.includes(currentStep)
      ? skippedSteps
      : [...skippedSteps, currentStep];
    setSkippedSteps(newSkipped);

    const nextStep = currentStep + 1;

    if (currentStep === TOTAL_STEPS) {
      // Skip final step = complete
      try {
        const res = await fetch("/api/portal/onboarding/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ step_data: stepData }),
        });
        if (!res.ok) {
          setError("Something went wrong. Please try again.");
          setLoading(false);
          return;
        }
      } catch {
        setError("Network error. Please try again.");
        setLoading(false);
        return;
      }
      setLoading(false);
      router.push("/portal");
      return;
    }

    setCurrentStep(nextStep);
    await saveProgress(nextStep, stepData, completedSteps, newSkipped);
    setLoading(false);
  }

  async function handleBack() {
    if (currentStep <= 1) return;
    const prevStep = currentStep - 1;
    setCurrentStep(prevStep);
    await saveProgress(prevStep, stepData, completedSteps, skippedSteps);
  }

  const stepProps = {
    stepData,
    onUpdate: handleUpdateStepData,
    onNext: handleNext,
    onSkip: handleSkip,
    onBack: handleBack,
    isFirst: currentStep === 1,
    isLast: currentStep === TOTAL_STEPS,
    loading,
  };

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-[#6C63FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Progress indicator */}
      <div className="flex items-center justify-between">
        {Array.from({ length: TOTAL_STEPS }).map((_, i) => {
          const stepNum = i + 1;
          const isActive = stepNum === currentStep;
          const isDone =
            completedSteps.includes(stepNum) ||
            skippedSteps.includes(stepNum);
          const isPast = stepNum < currentStep;
          return (
            <div key={stepNum} className="flex items-center flex-1">
              {/* Step dot */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-300 ${
                    isActive
                      ? "bg-[#6C63FF] text-white ring-4 ring-[#6C63FF]/20"
                      : isDone || isPast
                      ? "bg-[#00D4AA]/20 text-[#00D4AA] border border-[#00D4AA]/30"
                      : "bg-white/[0.04] text-[#4B5563] border border-white/[0.08]"
                  }`}
                >
                  {isDone || isPast ? (
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    stepNum
                  )}
                </div>
                <span
                  className={`text-[10px] mt-1.5 whitespace-nowrap ${
                    isActive
                      ? "text-[#B0B8C8] font-medium"
                      : "text-[#4B5563]"
                  }`}
                >
                  {STEP_LABELS[i]}
                </span>
              </div>

              {/* Connector line */}
              {stepNum < TOTAL_STEPS && (
                <div
                  className={`flex-1 h-px mx-2 mt-[-18px] transition-colors duration-300 ${
                    isPast || isDone
                      ? "bg-[#00D4AA]/30"
                      : "bg-white/[0.06]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div className="glass-card-static p-6 sm:p-8">
        {currentStep === 1 && <StepBusinessProfile {...stepProps} />}
        {currentStep === 2 && <StepConnectTools {...stepProps} />}
        {currentStep === 3 && <StepChooseAutomation {...stepProps} />}
        {currentStep === 4 && <StepPreview {...stepProps} />}
        {currentStep === 5 && (
          <StepActivate loading={loading} onActivate={handleNext} />
        )}

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-2 text-sm text-red-400 bg-red-500/5 border border-red-500/15 rounded-xl px-4 py-3 mt-4">
            <span className="flex-shrink-0 mt-0.5">!</span>
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Step counter */}
      <p className="text-center text-xs text-[#4B5563]">
        Step {currentStep} of {TOTAL_STEPS}
      </p>
    </div>
  );
}
