"use client";

import * as React from "react";
import { AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { Label } from "@/components/ui-shadcn/label";

export interface FieldProps extends React.ComponentProps<"div"> {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  htmlFor?: string;
}

function Field({
  label,
  hint,
  error,
  required,
  htmlFor,
  className,
  children,
  ...props
}: FieldProps) {
  const generatedId = React.useId();
  const fieldId = htmlFor ?? generatedId;
  const hasError = Boolean(error);

  return (
    <div
      data-slot="field"
      data-invalid={hasError ? "true" : undefined}
      className={cn("flex flex-col gap-2", className)}
      {...props}
    >
      {label ? (
        <Label
          htmlFor={fieldId}
          className={cn(
            "text-[0.8rem] font-semibold tracking-[0.5px] uppercase text-[var(--text-muted)]",
            hasError && "text-[var(--danger)]",
          )}
        >
          {label}
          {required ? <span aria-hidden className="ml-0.5 text-[var(--brand-primary)]">*</span> : null}
        </Label>
      ) : null}

      {React.isValidElement(children)
        ? React.cloneElement(
            children as React.ReactElement<{
              id?: string;
              "aria-invalid"?: boolean;
              "aria-describedby"?: string;
            }>,
            {
              id: (children as React.ReactElement<{ id?: string }>).props.id ?? fieldId,
              "aria-invalid": hasError || undefined,
              "aria-describedby":
                hasError ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined,
            },
          )
        : children}

      {hint && !hasError ? (
        <p id={`${fieldId}-hint`} className="text-xs text-[var(--text-dim)]">
          {hint}
        </p>
      ) : null}

      {hasError ? (
        <p
          id={`${fieldId}-error`}
          role="alert"
          className="flex items-center gap-1.5 text-xs font-medium text-[var(--danger)]"
        >
          <AlertCircle className="size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
    </div>
  );
}

export { Field };
