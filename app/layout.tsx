import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import Providers from "@/components/providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Orqentra — The Financial Operating System",
  description: "Next-generation autonomous financial operating system powered by elite orchestration engines.",
  keywords: ["Financial OS", "autonomous orchestration", "intelligent finance", "Orqentra", "FOS"],
  openGraph: {
    title: "Orqentra — The Financial Operating System",
    description: "Autonomous financial orchestration powered by the world's first FOS.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: "#0d1424",
                color: "#f8fafc",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: "12px",
                fontSize: "14px",
              },
              success: { iconTheme: { primary: "#10b981", secondary: "#0d1424" } },
              error: { iconTheme: { primary: "#f43f5e", secondary: "#0d1424" } },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
