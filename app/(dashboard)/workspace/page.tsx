import type { Metadata } from "next";
import WorkspaceLayout from "@/components/workspace/WorkspaceLayout";

export const metadata: Metadata = {
  title: "AI Workspace — AFOS",
  description:
    "Full-screen AI chat workspace powered by LangGraph multi-agent system. Ask questions about your finances, invoices, vendors, and more.",
};

/**
 * /workspace — AI Chatbot Workspace
 *
 * Full-screen conversational AI platform (ChatGPT-style).
 * Auth and org-context are guaranteed by the parent (dashboard) layout.
 * WorkspaceLayout is a client component that owns all interactive state.
 */
export default function WorkspacePage() {
  return (
    // Stretch to fill the dashboard main area (parent is flex-col, overflow-hidden)
    <div className="h-full -m-6">
      <WorkspaceLayout />
    </div>
  );
}
