import { PortalNav } from "@/components/portal/PortalNav";
import { ThemeProvider } from "@/lib/theme-provider";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeProvider>
      <PortalNav />
      <main
        className="portal-main"
        style={{
          marginLeft: "264px",
          minHeight: "100vh",
        }}
      >
        <div style={{ padding: "32px", maxWidth: "1400px" }}>
          {children}
        </div>
      </main>
    </ThemeProvider>
  );
}
