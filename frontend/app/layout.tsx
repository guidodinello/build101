import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Figtree } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
});

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Neitor AI",
  description: "Tu agencia de marketing en WhatsApp",
};

export const viewport: Viewport = {
  themeColor: "#faf7f2",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${figtree.variable} ${bricolage.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        {children}
        <Toaster theme="light" position="top-center" />
      </body>
    </html>
  );
}
