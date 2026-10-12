import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { ViewerBar, ViewerBarFallback } from "@/components/viewer-bar";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Review Health",
  description: "Whether code review is working, and whether review work is shared fairly.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-base-200 font-sans">
        <header className="navbar gap-4 bg-base-100 shadow-sm px-4">
          <Link href="/" className="flex-none text-lg font-semibold whitespace-nowrap">
            Review Health
          </Link>
          <Suspense fallback={<ViewerBarFallback />}>
            <ViewerBar />
          </Suspense>
        </header>
        <main className="flex-1 w-full max-w-6xl mx-auto p-6">{children}</main>
      </body>
    </html>
  );
}
