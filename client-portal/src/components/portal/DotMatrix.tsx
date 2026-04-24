// Fixed-position dot matrix overlay (mounted once by PortalShell).
// CSS class is defined in src/styles/utilities.css so it picks up theme changes.
export function DotMatrix() {
  return <div className="dot-matrix-bg" aria-hidden />;
}
