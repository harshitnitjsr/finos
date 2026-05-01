"use client";
import { useState } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import CommandPalette from "@/components/global/CommandPalette";
import ChatWidget from "@/components/global/ChatWidget";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--color-bg-primary)" }}>
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar onCommandOpen={() => setCommandOpen(true)} />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: "var(--color-bg-primary)" }}>
          {children}
        </main>
      </div>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      <ChatWidget />
    </div>
  );
}
