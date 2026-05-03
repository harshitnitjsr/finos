"use client";
import { useState } from "react";
import { Search, Bell, Globe, ChevronDown, LogOut, User, Settings } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useSession, signOut } from "next-auth/react";
import Image from "next/image";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

const CURRENCIES = ["USD", "INR", "EUR", "GBP", "JPY"];
const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥"
};

interface NotificationItem {
  id: string;
  title: string;
  type: string;
  time: string;
}

interface TopBarProps {
  onCommandOpen: () => void;
}

export default function TopBar({ onCommandOpen }: TopBarProps) {
  const [currency, setCurrency] = useState("USD");
  const [currencyOpen, setCurrencyOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const { data: notifData } = useQuery<{ notifications: NotificationItem[] }>({
    queryKey: ["notifications"],
    queryFn: async () => {
      const res = await fetch("/api/backend/analytics/notifications");
      if (!res.ok) throw new Error("Failed to fetch notifications");
      return res.json();
    },
    refetchInterval: 30000, // Poll every 30 seconds
  });

  const notifications = notifData?.notifications || [];
  const hasUnread = notifications.length > 0;

  return (
    <header
      className="flex items-center justify-between px-6 h-16 flex-shrink-0"
      style={{
        background: "var(--color-bg-secondary)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      {/* Search */}
      <button
        onClick={onCommandOpen}
        className="flex items-center gap-3 px-4 py-2 rounded-xl text-sm transition-all hover:border-blue-500/50"
        style={{
          background: "var(--color-bg-card)",
          border: "1px solid var(--color-border)",
          color: "var(--color-text-muted)",
          minWidth: 260,
        }}
      >
        <Search size={15} />
        <span>Search anything...</span>
        <span className="ml-auto text-xs px-1.5 py-0.5 rounded font-mono"
          style={{ background: "var(--color-bg-elevated)", color: "var(--color-text-muted)" }}>
          ⌘K
        </span>
      </button>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Currency Selector */}
        <div className="relative">
          <button
            onClick={() => setCurrencyOpen(!currencyOpen)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-all hover:border-blue-500/30"
            style={{
              background: "var(--color-bg-card)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-secondary)",
            }}
          >
            <Globe size={14} />
            <span>{CURRENCY_SYMBOLS[currency]} {currency}</span>
            <ChevronDown size={12} />
          </button>
          <AnimatePresence>
            {currencyOpen && (
              <motion.div
                initial={{ opacity: 0, y: -8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full mt-2 z-50 rounded-xl overflow-hidden"
                style={{
                  background: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border-hover)",
                  minWidth: 140,
                  boxShadow: "var(--shadow-elevated)",
                }}
              >
                {CURRENCIES.map((c) => (
                  <button
                    key={c}
                    onClick={() => { setCurrency(c); setCurrencyOpen(false); }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm transition-colors hover:bg-blue-500/10 text-left"
                    style={{ color: c === currency ? "#3b82f6" : "var(--color-text-secondary)" }}
                  >
                    <span className="font-semibold w-5">{CURRENCY_SYMBOLS[c]}</span>
                    <span>{c}</span>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative w-9 h-9 rounded-xl flex items-center justify-center transition-all"
            style={{
              background: "var(--color-bg-card)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-secondary)",
            }}
          >
            <Bell size={16} />
            {hasUnread && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-rose-500" />}
          </button>
          <AnimatePresence>
            {notifOpen && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full mt-2 z-50 rounded-xl"
                style={{
                  background: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border-hover)",
                  width: 320,
                  boxShadow: "var(--shadow-elevated)",
                }}
              >
                <div className="px-4 py-3 border-b" style={{ borderColor: "var(--color-border)" }}>
                  <span className="font-semibold text-sm text-white">Notifications</span>
                </div>
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-xs text-slate-400">No new notifications</div>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className="px-4 py-3 border-b hover:bg-blue-500/5 transition-colors cursor-pointer" style={{ borderColor: "var(--color-border)" }}>
                      <div className="flex items-start gap-3">
                        <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${n.type === 'warning' ? 'bg-amber-400' : n.type === 'danger' ? 'bg-rose-400' : 'bg-blue-400'}`} />
                        <div>
                          <p className="text-sm text-white font-medium">{n.title}</p>
                          <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>{n.time}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* User Menu */}
        <UserMenu />
      </div>
    </header>
  );
}

function UserMenu() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);

  const user = session?.user;
  const initials = user?.name
    ? user.name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : "U";

  return (
    <div className="relative">
      <button
        id="user-menu-btn"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-xl transition-all hover:bg-white/5"
        title={user?.name ?? "Account"}
      >
        {user?.image ? (
          <Image
            src={user.image}
            alt={user.name ?? "avatar"}
            width={32}
            height={32}
            className="w-8 h-8 rounded-xl object-cover ring-2 ring-indigo-500/30"
          />
        ) : (
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold text-white"
            style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}
          >
            {initials}
          </div>
        )}
        <div className="text-left hidden sm:block">
          <p className="text-xs font-semibold text-white leading-tight">{user?.name ?? "User"}</p>
          <p className="text-xs leading-tight" style={{ color: "var(--color-text-muted)" }}>
            {session?.user?.orgName ?? "No organisation"}
          </p>
        </div>
        <ChevronDown size={12} style={{ color: "var(--color-text-muted)" }} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 z-50 rounded-xl overflow-hidden"
            style={{
              background: "var(--color-bg-elevated)",
              border: "1px solid var(--color-border-hover)",
              minWidth: 200,
              boxShadow: "var(--shadow-elevated)",
            }}
          >
            {/* User info header */}
            <div className="px-4 py-3 border-b" style={{ borderColor: "var(--color-border)" }}>
              <p className="text-sm font-semibold text-white">{user?.name}</p>
              <p className="text-xs mt-0.5 truncate" style={{ color: "var(--color-text-muted)" }}>
                {user?.email}
              </p>
            </div>

            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 w-full px-4 py-2.5 text-sm transition-colors hover:bg-white/5"
              style={{ color: "var(--color-text-secondary)" }}
            >
              <Settings size={14} />
              Settings
            </Link>

            <div className="border-t" style={{ borderColor: "var(--color-border)" }} />

            <button
              id="signout-btn"
              onClick={() => {
                setOpen(false);
                signOut({ callbackUrl: "/" });
              }}
              className="flex items-center gap-3 w-full px-4 py-2.5 text-sm transition-colors hover:bg-rose-500/10 text-left"
              style={{ color: "#f87171" }}
            >
              <LogOut size={14} />
              Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
