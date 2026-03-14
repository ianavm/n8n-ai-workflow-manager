import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "AnyVision Media — Client Portal",
  description: "Monitor your AI workflows, track leads, and view analytics.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <div className="dot-bg" aria-hidden="true" />
        <div className="relative z-10 min-h-screen">{children}</div>
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "rgba(17, 24, 39, 0.95)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              color: "#B0B8C8",
              backdropFilter: "blur(20px)",
            },
          }}
        />
      </body>
    </html>
  );
}
