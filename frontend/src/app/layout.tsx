import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Notifications } from "@/components/notifications";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Newsroom AI",
  description: "AI 기반 뉴스룸 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex">
        <Sidebar />
        <main className="flex-1 ml-56">
          <header className="sticky top-0 z-20 flex h-14 items-center justify-end border-b bg-background/80 px-6 backdrop-blur">
            <Notifications />
          </header>
          <div className="p-6">{children}</div>
        </main>
      </body>
    </html>
  );
}
