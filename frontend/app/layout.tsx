import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "vietnamese"],
});

export const metadata: Metadata = {
  title: "Hệ thống Phân tích Nội soi AI",
  description: "Dashboard phân tích nội soi thông minh theo thời gian thực",
};

import NavBar from "../components/NavBar";
import Footer from "../components/Footer";
import { AnalysisProvider } from "@/context/AnalysisContext";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="dark h-full">
      <body className={`${inter.className} ${inter.variable} min-h-full font-sans antialiased flex flex-col`}>
        <AnalysisProvider>
          <NavBar />
          <main className="relative flex-1">{children}</main>
          <Footer />
        </AnalysisProvider>
      </body>
    </html>
  );
}
