import type { Metadata } from "next";
import { IBM_Plex_Mono, Source_Sans_3, Space_Grotesk } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { OnboardingRail } from "@/components/OnboardingRail";
import { SiteNav } from "@/components/SiteNav";

const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display", weight: ["500", "600", "700"] });
const body = Source_Sans_3({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "600", "700"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "Imparency",
  description: "A donation ledger you can actually read: every rupee traced from your hand to a verified NGO.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body className="min-h-screen font-sans antialiased">
        <header className="border-b-2 border-navy bg-paper">
          <nav className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-5" aria-label="Primary">
            <Link href="/" className="font-display text-xl font-semibold tracking-tight text-navy">
              Imparency<span className="text-teal">.</span>
            </Link>
            <SiteNav />
          </nav>
        </header>

        <main className="mx-auto max-w-5xl px-4 py-10">{children}</main>

        <OnboardingRail />

        <footer className="mt-16 border-t-2 border-navy bg-navy text-paper/80">
          <div className="mx-auto max-w-5xl space-y-3 px-4 py-8 text-sm">
            <p className="font-display text-base text-paper">Imparency</p>
            <p className="max-w-xl">
              Every donation on this page is a ledger entry: who gave, who received it, and who verified the receiver.
              Nothing is marked verified without a person checking it first.
            </p>
            <p className="pt-2 text-xs text-paper/60">
              <Link href="/admin/login" className="underline decoration-paper/30 hover:text-paper hover:decoration-paper">
                Platform staff sign-in
              </Link>
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
