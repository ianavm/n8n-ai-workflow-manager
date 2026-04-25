import Link from "next/link";
import { Shield } from "lucide-react";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-base)]">
      <header className="border-b border-[var(--border-subtle)] backdrop-blur-md bg-[var(--bg-elevated)]/70">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/portal/login" className="flex items-center gap-2.5 group">
            <span
              aria-hidden
              className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]"
            >
              <Shield className="size-4 text-white" />
            </span>
            <span className="text-sm font-bold tracking-[0.08em] text-foreground">
              ANYVISION
            </span>
          </Link>
          <nav className="flex items-center gap-5 text-xs text-[var(--text-muted)]">
            <Link href="/legal/privacy" className="hover:text-foreground transition-colors">
              Privacy
            </Link>
            <Link href="/legal/terms" className="hover:text-foreground transition-colors">
              Terms
            </Link>
            <Link href="/portal/login" className="hover:text-foreground transition-colors">
              Sign in &rarr;
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-12">
        {children}
      </main>

      <footer className="border-t border-[var(--border-subtle)] py-6 text-center text-xs text-[var(--text-dim)]">
        © {new Date().getFullYear()} AnyVision Media (Pty) Ltd · Johannesburg, South Africa
      </footer>
    </div>
  );
}
