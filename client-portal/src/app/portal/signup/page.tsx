import Link from "next/link";
import { Lock, ShieldCheck } from "lucide-react";

export default function SignupPage() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-6 py-12"
      style={{ background: "#0A0F1C", color: "#fff", fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div
        className="w-full max-w-[440px] rounded-2xl p-8"
        style={{ background: "#111827", border: "1px solid #1F2937" }}
      >
        <div className="flex items-center gap-2 mb-6">
          <span
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg font-extrabold"
            style={{ background: "linear-gradient(135deg, #6C63FF, #00D4AA)" }}
          >
            A
          </span>
          <span className="text-[18px] font-bold">AnyVision</span>
        </div>

        <h1 className="text-[22px] font-bold mb-3">Signups are closed</h1>
        <p className="text-[14px] leading-relaxed mb-6" style={{ color: "#B0B8C8" }}>
          The AnyVision portal is currently invite-only while we onboard new
          clients directly. To request access, email{" "}
          <a
            href="mailto:ian@anyvisionmedia.com?subject=Portal access request"
            style={{ color: "#6C63FF" }}
            className="underline"
          >
            ian@anyvisionmedia.com
          </a>
          .
        </p>

        <div className="flex flex-col gap-3">
          <Link
            href="/portal/login"
            className="block w-full text-center rounded-xl py-3 text-[14px] font-semibold"
            style={{ background: "linear-gradient(135deg, #6C63FF, #00D4AA)", color: "#fff" }}
          >
            I already have an account &rarr;
          </Link>
          <a
            href="https://www.anyvisionmedia.com"
            className="block w-full text-center rounded-xl py-3 text-[14px] font-medium"
            style={{ border: "1px solid #1F2937", color: "#B0B8C8" }}
          >
            Back to anyvisionmedia.com
          </a>
        </div>
      </div>

      <div className="flex items-center gap-6 mt-8 text-[12px]" style={{ color: "#52525B" }}>
        <div className="flex items-center gap-1.5">
          <Lock size={13} />
          <span>256-bit encrypted</span>
        </div>
        <div className="flex items-center gap-1.5">
          <ShieldCheck size={13} />
          <span>POPIA compliant</span>
        </div>
      </div>
    </div>
  );
}
