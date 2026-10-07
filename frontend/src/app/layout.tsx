import "@fontsource-variable/inter";
import "@fontsource/oswald/500.css";
import "@fontsource/oswald/600.css";
import "@fontsource/oswald/700.css";
import "./globals.css";

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "NFL Bracket Battle", template: "%s · NFL Bracket Battle" },
  description: "Das private NFL-Playoff-Tippspiel",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#04060c",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
