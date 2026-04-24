"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "framer-motion";
import { forwardRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface RevealProps extends Omit<HTMLMotionProps<"div">, "initial" | "animate" | "transition"> {
  children: ReactNode;
  /** Delay in 100ms steps (0-5) — matches website .reveal-delay-* classes. */
  delay?: 0 | 1 | 2 | 3 | 4 | 5;
  as?: "div" | "section" | "article";
  className?: string;
}

/**
 * On-mount reveal animation (fade + slight slide). Mirrors the website's
 * `.reveal` / `.reveal-delay-*` treatment. Respects prefers-reduced-motion.
 */
export const Reveal = forwardRef<HTMLDivElement, RevealProps>(function Reveal(
  { children, delay = 0, className, ...rest },
  ref,
) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      ref={ref}
      className={cn(className)}
      initial={reduced ? false : { opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduced ? 0 : 0.6,
        delay: reduced ? 0 : delay * 0.1,
        ease: [0.16, 1, 0.3, 1],
      }}
      {...rest}
    >
      {children}
    </motion.div>
  );
});
