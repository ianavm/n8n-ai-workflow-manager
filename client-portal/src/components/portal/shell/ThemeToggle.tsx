"use client";

import { Moon, Sun } from "lucide-react";
import { useColorScheme } from "@/lib/providers/ColorSchemeProvider";
import { Button } from "@/components/ui-shadcn/button";

export function ThemeToggle() {
  const { scheme, toggle } = useColorScheme();
  const isDark = scheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
    >
      {isDark ? <Moon className="size-4" /> : <Sun className="size-4" />}
    </Button>
  );
}
