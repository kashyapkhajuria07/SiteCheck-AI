import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SiteCheck AI",
  description: "AI-powered construction site inspection",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
