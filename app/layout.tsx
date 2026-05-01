import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import Providers from "@/components/providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AFOS — AI Financial Operating System",
  description: "Autonomous Financial Operating System. AI-native financial execution infrastructure.",
  keywords: ["AI finance", "autonomous finance", "invoice processing", "expense management"],
  openGraph: {
    title: "AFOS — AI Financial Operating System",
    description: "Autonomous Financial Operating System powered by AI agents",
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
