/**
 * Root layout: wraps every page with the top navigation.
 * Page files live in app/<route>/page.tsx (Next.js App Router).
 */

import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "FAQ Auto Builder",
  description: "Turn resolved support tickets into reviewed knowledge-base FAQs",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
