import { FileText } from "lucide-react";
import Link from "next/link";

export const metadata = {
  title: "Terms of Service · AnyVision Media",
  description:
    "AnyVision Media client portal terms of service. South African law, ZAR billing, POPIA compliance.",
};

export default function TermsOfServicePage() {
  return (
    <div className="max-w-3xl space-y-8">
      <div className="flex items-center gap-3">
        <FileText size={24} className="text-[var(--brand-primary)]" />
        <h1 className="text-2xl font-bold text-white">Terms of Service</h1>
      </div>

      <div className="glass-card p-8 space-y-6 text-sm text-[#A1A1AA] leading-relaxed">
        <p className="text-xs text-[#52525B]">Last updated: April 2026</p>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">1. Agreement</h2>
          <p>
            By accessing and using the AnyVision Media client portal (&quot;the Service&quot;),
            you agree to be bound by these Terms of Service. If you do not agree to these terms,
            please do not use the Service.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">2. Service Description</h2>
          <p>
            AnyVision Media provides AI-powered workflow automation, marketing intelligence,
            and business management tools through our cloud-based portal. The Service includes
            dashboard analytics, workflow management, billing, and related features as described
            in your subscription plan.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">3. Account Responsibilities</h2>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>You are responsible for maintaining the confidentiality of your login credentials</li>
            <li>You must provide accurate and complete account information</li>
            <li>You must notify us immediately of any unauthorized access</li>
            <li>You are responsible for all activity under your account</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">4. Acceptable Use</h2>
          <p>You agree not to:</p>
          <ul className="list-disc list-inside space-y-1 ml-2 mt-2">
            <li>Use the Service for unlawful purposes</li>
            <li>Attempt to gain unauthorized access to any part of the Service</li>
            <li>Interfere with or disrupt the Service&apos;s infrastructure</li>
            <li>Transmit malware, viruses, or harmful code</li>
            <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">5. Billing and Payments</h2>
          <p>
            Subscription fees are billed according to your chosen plan. All amounts are in
            South African Rand (ZAR) and include 15% VAT where applicable. Payments are processed
            securely through Stripe or PayFast. You may cancel your subscription at any time,
            effective at the end of your current billing period.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">6. Data and Privacy</h2>
          <p>
            Your use of the Service is also governed by our{" "}
            <Link href="/legal/privacy" className="text-[var(--brand-primary)] no-underline hover:underline">
              Privacy Policy
            </Link>.
            We process personal information in compliance with the Protection of Personal
            Information Act (POPIA), 2013.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">7. Service Availability</h2>
          <p>
            We strive to maintain high availability but do not guarantee uninterrupted access.
            We may perform maintenance that temporarily affects Service availability. We will
            provide reasonable notice of planned downtime where possible.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">8. Limitation of Liability</h2>
          <p>
            To the maximum extent permitted by South African law, AnyVision Media shall not
            be liable for any indirect, incidental, special, or consequential damages arising
            from your use of the Service.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">9. Governing Law</h2>
          <p>
            These Terms are governed by the laws of the Republic of South Africa. Any disputes
            shall be subject to the jurisdiction of the courts of Gauteng, South Africa.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">10. Contact</h2>
          <p>
            For questions about these Terms, contact us at:
          </p>
          <p className="mt-2 text-white">
            Email: ian@anyvisionmedia.com
          </p>
        </section>
      </div>

      <div className="flex gap-4 text-sm text-[#52525B]">
        <Link href="/legal/privacy" className="hover:text-[#71717A] no-underline">
          Privacy Policy &rarr;
        </Link>
        <Link href="/portal/login" className="hover:text-[#71717A] no-underline">
          Back to Sign in
        </Link>
      </div>
    </div>
  );
}
