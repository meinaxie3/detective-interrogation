import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Detective Interrogation Room",
  description: "AI-powered murder mystery interrogation game",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
