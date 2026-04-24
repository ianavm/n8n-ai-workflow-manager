"use client";

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui-shadcn/sheet";
import { Sidebar } from "@/components/portal/shell/Sidebar";

interface MobileSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        className="w-[var(--sidebar-w)] p-0 border-r border-[var(--sidebar-border)] max-w-[85vw]"
        showCloseButton={false}
      >
        <SheetHeader className="sr-only">
          <SheetTitle>Navigation</SheetTitle>
          <SheetDescription>Main portal navigation menu</SheetDescription>
        </SheetHeader>
        <Sidebar
          collapsed={false}
          onToggle={() => {}}
          hideCollapse
          onNavigate={() => onOpenChange(false)}
          className="h-full w-full"
        />
      </SheetContent>
    </Sheet>
  );
}
