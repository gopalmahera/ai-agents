import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import Shell from "@/components/shell/Shell";

export const metadata: Metadata = {
  title: "AI Alert Agent Console",
  description: "Configuration and monitoring dashboard for AI Alert Agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
