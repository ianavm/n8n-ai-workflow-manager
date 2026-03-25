import { PortalNav } from "@/components/portal/PortalNav";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <PortalNav />
      {/* Main content area with dot matrix background (V1 preview) */}
      <main
        className="portal-main"
        style={{
          marginLeft: "264px",
          minHeight: "100vh",
          position: "relative",
          backgroundImage: "radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      >
        <div style={{ padding: "32px", maxWidth: "1400px" }}>
          {children}
        </div>
      </main>
    </>
  );
}
