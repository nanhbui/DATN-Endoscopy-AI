'use client';

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { theme } from '@/lib/theme';
import NavBar from "../components/NavBar";
import Footer from "../components/Footer";
import { AnalysisProvider } from "@/context/AnalysisContext";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "vietnamese"],
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <head>
        <title>Hệ thống Phân tích Nội soi AI</title>
        <meta name="description" content="Dashboard phân tích nội soi thông minh theo thời gian thực" />
      </head>
      <body className={`${inter.className} ${inter.variable}`}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <AnalysisProvider>
            <NavBar />
            <main style={{ flex: 1, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
              {children}
            </main>
            <Footer />
          </AnalysisProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
