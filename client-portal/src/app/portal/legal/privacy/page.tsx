import { Shield } from "lucide-react";
import Link from "next/link";

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <div className="flex items-center gap-3">
        <Shield size={24} className="text-[#6366F1]" />
        <h1 className="text-2xl font-bold text-white">Privacy Policy</h1>
      </div>

      <div className="glass-card p-8 space-y-6 text-sm text-[#A1A1AA] leading-relaxed">
        <p className="text-xs text-[#52525B]">Last updated: April 2026</p>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">1. Introduction</h2>
          <p>
            AnyVision Media (Pty) Ltd (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) is committed to protecting
            your personal information in accordance with the Protection of Personal Information Act
            (POPIA), 2013, and other applicable data protection laws of South Africa.
          </p>
          <p className="mt-2">
            This Privacy Policy explains how we collect, use, store, and protect your personal
            information when you use our client portal and related services.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">2. Information We Collect</h2>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>Account information (name, email, company name, phone number)</li>
            <li>Authentication data (encrypted passwords, login timestamps, IP addresses)</li>
            <li>Usage data (page views, feature interactions, workflow configurations)</li>
            <li>Billing information (subscription status, payment history via secure processors)</li>
            <li>Communication data (support tickets, preferences)</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">3. How We Use Your Information</h2>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>To provide and maintain our services</li>
            <li>To authenticate your identity and manage your account</li>
            <li>To process billing and subscriptions</li>
            <li>To send service-related communications</li>
            <li>To improve our platform and user experience</li>
            <li>To comply with legal obligations</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">4. Data Protection (POPIA Compliance)</h2>
          <p>
            As a responsible party under POPIA, we ensure that:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2 mt-2">
            <li>Personal information is processed lawfully and in a reasonable manner</li>
            <li>Data is collected for a specific, explicitly defined purpose</li>
            <li>We do not retain personal information longer than necessary</li>
            <li>Appropriate technical and organizational security measures are in place</li>
            <li>You have the right to access, correct, or delete your personal information</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">5. Data Security</h2>
          <p>
            We implement industry-standard security measures including:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2 mt-2">
            <li>256-bit TLS encryption for all data in transit</li>
            <li>AES-256 encryption for data at rest</li>
            <li>Row-level security (RLS) database policies</li>
            <li>Rate limiting on authentication endpoints</li>
            <li>Automatic session timeout after 30 minutes of inactivity</li>
            <li>Regular security audits and monitoring</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">6. Third-Party Services</h2>
          <p>
            We use the following third-party services that may process your data:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2 mt-2">
            <li>Supabase (authentication and database hosting)</li>
            <li>Stripe and PayFast (payment processing)</li>
            <li>Vercel (application hosting)</li>
            <li>Google (OAuth authentication, where enabled)</li>
          </ul>
          <p className="mt-2">
            Each provider is contractually bound to handle your data securely and in compliance
            with applicable data protection regulations.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">7. Your Rights</h2>
          <p>Under POPIA, you have the right to:</p>
          <ul className="list-disc list-inside space-y-1 ml-2 mt-2">
            <li>Request access to your personal information</li>
            <li>Request correction of inaccurate information</li>
            <li>Request deletion of your personal information</li>
            <li>Object to the processing of your personal information</li>
            <li>Lodge a complaint with the Information Regulator</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-white mb-2">8. Contact Us</h2>
          <p>
            For privacy-related inquiries or to exercise your rights, contact us at:
          </p>
          <p className="mt-2 text-white">
            Email: ian@anyvisionmedia.com
          </p>
        </section>
      </div>

      <div className="flex gap-4 text-sm text-[#52525B]">
        <Link href="/portal/legal/terms" className="hover:text-[#71717A] no-underline">
          Terms of Service &rarr;
        </Link>
        <Link href="/portal/settings" className="hover:text-[#71717A] no-underline">
          Back to Settings
        </Link>
      </div>
    </div>
  );
}
