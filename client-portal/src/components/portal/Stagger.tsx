"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface StaggerProps {
  children: ReactNode;
  className?: string;
  /** Delay between each child's entrance (seconds). Default 0.06s. */
  stagger?: number;
  /** Initial delay for the first child. */
  delayChildren?: number;
}

const parent = (stagger: number, delayChildren: number) => ({
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: { staggerChildren: stagger, delayChildren },
  },
});

const child = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
  },
};

/**
 * Stagger children's entrance. Wrap with <StaggerItem> inside.
 * Each direct child of `Stagger.Item` inherits the cascade.
 */
export function Stagger({ children, className, stagger = 0.06, delayChildren = 0 }: StaggerProps) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={cn(className)}>{children}</div>;

  return (
    <motion.div
      className={cn(className)}
      variants={parent(stagger, delayChildren)}
      initial="hidden"
      animate="show"
    >
      {children}
    </motion.div>
  );
}

interface StaggerItemProps {
  children: ReactNode;
  className?: string;
}

export function StaggerItem({ children, className }: StaggerItemProps) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={cn(className)}>{children}</div>;
  return (
    <motion.div className={cn(className)} variants={child}>
      {children}
    </motion.div>
  );
}
