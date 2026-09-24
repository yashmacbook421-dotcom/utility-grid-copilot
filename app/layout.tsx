import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Utility Grid Copilot",
  description: "Demand forecasting and grid-ops recommendations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
