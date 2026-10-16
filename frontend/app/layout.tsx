import type { Metadata, Viewport } from "next";
import { Shell } from "@/components/Shell";
import { DEFAULT_LOCALE, directionOf } from "@/lib/locale";
import "./globals.css";

export const metadata: Metadata = {
  title: "ElectionSimulationAI",
  description:
    "شبیه‌سازی فرضی انتخابات و تحلیل آماری بر پایهٔ فرض‌های اعلام‌شده. Hypothetical election simulation, not a forecast.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={DEFAULT_LOCALE} dir={directionOf(DEFAULT_LOCALE)}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
