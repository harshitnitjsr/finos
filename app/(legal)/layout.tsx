import React from "react";
import Link from "next/link";
import { ArrowLeft, Zap } from "lucide-react";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen bg-[#020617] text-white selection:bg-emerald-500/30 overflow-x-hidden font-sans">
      {/* Noise Texture Overlay */}
      <div className="fixed inset-0 z-50 pointer-events-none noise opacity-50" />

      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-0 bg-grid opacity-20" />
        
        {/* Animated Aurora Blobs */}
        <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] rounded-full bg-emerald-600/10 blur-[120px]" />
        <div className="absolute bottom-[-15%] right-[-5%] w-[55%] h-[55%] rounded-full bg-lime-600/5 blur-[150px]" />
      </div>

      {/* Navigation */}
      <nav className="fixed top-8 left-1/2 -translate-x-1/2 w-[92%] max-w-6xl border border-white/5 bg-[#050810]/60 backdrop-blur-2xl z-50 px-6 py-3.5 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2.5 group cursor-pointer flex-shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-lime-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 group-hover:rotate-12 transition-transform duration-500">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-black tracking-tight shiny-text uppercase">Orqentra</span>
          </Link>

          <div className="flex items-center gap-4 flex-shrink-0">
            <Link 
              href="/"
              className="group flex items-center gap-2 px-4 py-2 bg-white/5 text-white text-[10px] font-black tracking-wider uppercase rounded-xl hover:bg-white/10 transition-all duration-300"
            >
              <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
              Back to System
            </Link>
          </div>
        </div>
      </nav>

      {/* Content Container */}
      <main className="relative z-10 pt-48 pb-32 px-6">
        <div className="max-w-4xl mx-auto p-12 rounded-[2.5rem] bg-[#050810]/80 backdrop-blur-xl border border-white/5 shadow-2xl">
          {children}
        </div>
      </main>
    </div>
  );
}
