"use client";

import { forwardRef, type InputHTMLAttributes } from "react";

import { Field } from "@/components/ui-shadcn/field";
import { Input as ShadcnInput } from "@/components/ui-shadcn/input";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

/**
 * Legacy Input API preserved for admin. Renders via Field + ShadcnInput
 * so admin picks up the coral focus glow + proper aria wiring.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");
    const input = <ShadcnInput ref={ref} id={inputId} {...props} />;

    if (!label && !error) return input;
    return (
      <Field label={label} error={error} htmlFor={inputId}>
        {input}
      </Field>
    );
  },
);

Input.displayName = "Input";
