import { PortalProviders } from "@/lib/providers/PortalProviders";
import { PortalShell } from "@/components/portal/shell/PortalShell";
import { DotMatrix } from "@/components/portal/DotMatrix";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PortalProviders>
      <DotMatrix />
      <PortalShell>{children}</PortalShell>
    </PortalProviders>
  );
}
