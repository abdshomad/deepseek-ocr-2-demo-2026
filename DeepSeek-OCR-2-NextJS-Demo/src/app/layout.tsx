import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeepSeek OCR 2 - Premium Next.js Interface",
  description: "High-fidelity document layout analysis, causal flow text recognition, and grounding visualizer powered by DeepSeek-OCR-2.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

