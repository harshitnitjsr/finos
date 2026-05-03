"use client";
import { useState } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import CommandPalette from "@/components/global/CommandPalette";
import GlobalBackground from "@/components/global/GlobalBackground";
import ChatWidget from "@/components/global/ChatWidget";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden relative" style={{ background: "var(--color-bg-primary)" }}>
      <GlobalBackground showParticles={false} />
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        <TopBar onCommandOpen={() => setCommandOpen(true)} />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: "transparent" }}>
          {children}
        </main>
      </div>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      <ChatWidget />
    </div>
  );
}
