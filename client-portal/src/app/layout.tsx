import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemedToaster } from "@/components/ThemedToaster";
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

// Runs before React hydrates so the correct color scheme is applied
// synchronously — prevents a flash of the wrong theme on refresh.
const colorSchemeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem('portal-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var useLight = stored === 'light' || (!stored && !prefersDark);
    if (useLight) document.documentElement.classList.add('light');
    document.documentElement.style.colorScheme = useLight ? 'light' : 'dark';
  } catch (e) {}
})();
`.trim();

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: colorSchemeInitScript }} />
      </head>
      <body className={`${inter.variable} font-sans antialiased`}>
        <div className="relative min-h-screen">{children}</div>
        <ThemedToaster />
      </body>
    </html>
  );
}
