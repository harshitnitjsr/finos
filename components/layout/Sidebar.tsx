"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, FileText, CreditCard, CheckSquare, Workflow,
  Bot, Landmark, BarChart3, Settings, ChevronLeft, ChevronRight,
  Zap, Shield, MessageSquare, Building2
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard", group: "main" },
  { href: "/invoices", icon: FileText, label: "Invoices", group: "main" },
  { href: "/expenses", icon: CreditCard, label: "Expenses", group: "main" },
  { href: "/approvals", icon: CheckSquare, label: "Approvals", group: "main", badge: "3" },
  { href: "/vendors", icon: Building2, label: "Vendors", group: "main" },
  { href: "/workflows", icon: Workflow, label: "Workflows", group: "ops" },
  { href: "/agents", icon: Bot, label: "AI Agents", group: "ops" },
  { href: "/workspace", icon: MessageSquare, label: "AI Workspace", group: "ops", aiLabel: true },
  { href: "/treasury", icon: Landmark, label: "Treasury", group: "ops" },
  { href: "/analytics", icon: BarChart3, label: "Analytics", group: "ops" },
  { href: "/settings", icon: Settings, label: "Settings", group: "config" },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <motion.aside
      animate={{ width: collapsed ? 68 : 240 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="flex-shrink-0 flex flex-col relative"
      style={{
        background: "var(--color-bg-secondary)",
        borderRight: "1px solid var(--color-border)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: "var(--color-border)" }}>
        <div className="w-8 h-8 rounded-lg animated-gradient flex items-center justify-center flex-shrink-0">
          <span className="text-white font-black text-sm">∞</span>
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.15 }}
            >
              <div className="font-black text-white text-base tracking-tight">AFOS</div>
              <div className="text-xs font-medium" style={{ color: "var(--color-text-muted)" }}>Financial OS</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {/* Main section */}
        {!collapsed && (
          <div className="mb-2 px-3">
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
              Core
            </span>
          </div>
        )}
        {NAV_ITEMS.filter(i => i.group === "main").map((item) => (
          <NavItem key={item.href} item={item} collapsed={collapsed} active={pathname === item.href} />
        ))}

        <div className="my-3 border-t" style={{ borderColor: "var(--color-border)" }} />
        {!collapsed && (
          <div className="mb-2 px-3">
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
              Operations
            </span>
          </div>
        )}
        {NAV_ITEMS.filter(i => i.group === "ops").map((item) => (
          <NavItem key={item.href} item={item} collapsed={collapsed} active={pathname === item.href} />
        ))}

        <div className="my-3 border-t" style={{ borderColor: "var(--color-border)" }} />
        {NAV_ITEMS.filter(i => i.group === "config").map((item) => (
          <NavItem key={item.href} item={item} collapsed={collapsed} active={pathname === item.href} />
        ))}
      </nav>

      {/* Agent Status */}
      {!collapsed && (
        <div className="flex-shrink-0 px-3 py-3 mx-3 mb-3 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)" }}>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-emerald flex-shrink-0" />
            <span className="text-xs font-bold truncate" style={{ color: "#10b981" }}>8 Agents Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Zap size={9} style={{ color: "var(--color-text-muted)" }} className="flex-shrink-0" />
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>All systems operational</span>
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <button
        onClick={onToggle}
        className="absolute -right-3 top-7 w-6 h-6 rounded-full flex items-center justify-center transition-all hover:scale-110"
        style={{
          background: "var(--color-bg-elevated)",
          border: "1px solid var(--color-border-hover)",
          color: "var(--color-text-secondary)",
        }}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </motion.aside>
  );
}

function NavItem({ item, collapsed, active }: { item: typeof NAV_ITEMS[0]; collapsed: boolean; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={`sidebar-nav-item ${active ? "active" : ""}`}
      title={collapsed ? item.label : undefined}
    >
      {/* AI Workspace gets a gradient icon */}
      {(item as {aiLabel?: boolean}).aiLabel ? (
        <span
          className="flex-shrink-0 w-[18px] h-[18px] flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            borderRadius: 5,
            padding: 2,
          }}
        >
          <item.icon size={12} className="text-white" />
        </span>
      ) : (
        <item.icon size={18} className="flex-shrink-0" />
      )}
      <AnimatePresence>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 text-sm"
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
      {!collapsed && item.badge && (
        <motion.span
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className="badge badge-danger text-xs px-2 py-0.5"
        >
          {item.badge}
        </motion.span>
      )}
    </Link>
  );
}
