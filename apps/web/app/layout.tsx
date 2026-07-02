import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import Shell from "@/components/shell/Shell";

export const metadata: Metadata = {
  title: "DAI Console",
  description: "Dozee Alert Intelligence — configuration and monitoring dashboard",
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
