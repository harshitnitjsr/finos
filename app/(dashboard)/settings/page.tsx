"use client";
import { useSession, signOut } from "next-auth/react";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  Settings as SettingsIcon, Shield, Building, Bell,
  LogOut, Save, Loader2, CheckCircle2, User, Mail,
  Globe, Calendar, DollarSign, CreditCard,
} from "lucide-react";
import toast from "react-hot-toast";
import BillingTab from "@/components/BillingTab";

const cv = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const iv = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

type Tab = "profile" | "organisation" | "notifications" | "billing";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "profile", label: "Profile & Security", icon: Shield },
  { id: "organisation", label: "Organisation", icon: Building },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "billing", label: "Billing & Usage", icon: CreditCard },
];

/* ── Profile Tab ─────────────────────────────────────────────────────────── */

function ProfileTab() {
  const { data: session } = useSession();
  const user = session?.user;

  return (
    <div className="p-6 space-y-6">
      {/* Avatar + name */}
      <div className="flex items-center gap-4 p-4 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
        {user?.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.image} alt={user.name ?? ""} className="w-16 h-16 rounded-full ring-2 ring-blue-500/30" />
        ) : (
          <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold text-white" style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}>
            {user?.name?.[0] ?? "?"}
          </div>
        )}
        <div>
          <p className="text-lg font-bold text-white">{user?.name ?? "—"}</p>
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Google Account</p>
        </div>
      </div>

      {/* Info rows */}
      <div className="space-y-3">
        {[
          { icon: User, label: "Full Name", value: user?.name ?? "—" },
          { icon: Mail, label: "Email", value: user?.email ?? "—" },
          { icon: Shield, label: "Role", value: user?.role ?? "owner" },
          { icon: Building, label: "Organisation ID", value: user?.orgId ? `${user.orgId.slice(0, 8)}…` : "—" },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
            <div className="flex items-center gap-2">
              <Icon size={14} style={{ color: "var(--color-text-muted)" }} />
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{label}</span>
            </div>
            <span className="text-sm font-medium text-white">{value}</span>
          </div>
        ))}
      </div>

      {/* Auth provider note */}
      <div className="p-4 rounded-xl" style={{ background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)" }}>
        <p className="text-xs text-blue-400 font-medium mb-1">Authentication</p>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Your account is managed via <strong className="text-white">Google OAuth</strong>. To change your name or profile photo, update your Google account directly.
        </p>
      </div>

      {/* Sign out */}
      <button
        id="settings-signout-btn"
        onClick={() => signOut({ callbackUrl: "/auth/signin" })}
        className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
        style={{ background: "rgba(244,63,94,0.1)", color: "#f43f5e", border: "1px solid rgba(244,63,94,0.2)" }}
      >
        <LogOut size={14} /> Sign Out
      </button>
    </div>
  );
}

/* ── Organisation Tab ────────────────────────────────────────────────────── */

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD"];
const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

function OrganisationTab() {
  const { data: session, update } = useSession();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [orgName, setOrgName] = useState(session?.user?.orgName ?? "");
  const [currency, setCurrency] = useState("USD");
  const [fiscalMonth, setFiscalMonth] = useState(1);

  const handleSave = async () => {
    if (!orgName.trim()) { toast.error("Organisation name cannot be empty"); return; }
    setSaving(true);
    try {
      const res = await fetch("/api/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ orgName, defaultCurrency: currency, fiscalYearStart: fiscalMonth }),
      });
      if (!res.ok) throw new Error((await res.json()).error ?? "Save failed");
      const data = await res.json();
      await update({ orgId: data.orgId, orgName: data.orgName, onboardingComplete: true });
      setSaved(true);
      toast.success("Organisation updated");
      setTimeout(() => setSaved(false), 3000);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <div>
        <label className="block text-xs font-semibold mb-1.5" style={{ color: "var(--color-text-muted)" }}>
          <Building size={12} className="inline mr-1" />Organisation Name
        </label>
        <input
          id="settings-org-name"
          value={orgName}
          onChange={e => setOrgName(e.target.value)}
          className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none transition-all"
          style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}
          placeholder="Acme Corp"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold mb-1.5" style={{ color: "var(--color-text-muted)" }}>
          <DollarSign size={12} className="inline mr-1" />Default Currency
        </label>
        <select
          id="settings-currency"
          value={currency}
          onChange={e => setCurrency(e.target.value)}
          className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none appearance-none"
          style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}
        >
          {CURRENCIES.map(c => <option key={c} value={c} style={{ background: "#0d1424" }}>{c}</option>)}
        </select>
      </div>

      <div>
        <label className="block text-xs font-semibold mb-1.5" style={{ color: "var(--color-text-muted)" }}>
          <Calendar size={12} className="inline mr-1" />Fiscal Year Start
        </label>
        <select
          id="settings-fiscal"
          value={fiscalMonth}
          onChange={e => setFiscalMonth(Number(e.target.value))}
          className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none appearance-none"
          style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}
        >
          {MONTHS.map((m, i) => <option key={m} value={i + 1} style={{ background: "#0d1424" }}>{m}</option>)}
        </select>
      </div>

      <div className="p-3 rounded-xl text-xs" style={{ background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)", color: "var(--color-text-secondary)" }}>
        <Globe size={12} className="inline mr-1 text-blue-400" />
        Organisation ID: <span className="font-mono text-white">{session?.user?.orgId ?? "—"}</span>
      </div>

      <button
        id="settings-save-org"
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-60 hover:opacity-90"
        style={{ background: saved ? "rgba(16,185,129,0.15)" : "rgba(59,130,246,0.15)", color: saved ? "#10b981" : "#3b82f6", border: `1px solid ${saved ? "rgba(16,185,129,0.3)" : "rgba(59,130,246,0.3)"}` }}
      >
        {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <CheckCircle2 size={14} /> : <Save size={14} />}
        {saving ? "Saving…" : saved ? "Saved!" : "Save Changes"}
      </button>
    </div>
  );
}

/* ── Notifications Tab ───────────────────────────────────────────────────── */

function NotificationsTab() {
  return (
    <div className="p-6 space-y-4">
      <div
        className="p-4 rounded-xl space-y-2"
        style={{ background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)" }}
      >
        <p className="text-sm font-semibold text-white flex items-center gap-2">
          <Bell size={14} className="text-blue-400" />
          In-App Notifications
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Risk alerts, approval requests, and workflow events are delivered via the bell icon in the top bar. They are fetched in real time from your organization&apos;s activity feed.
        </p>
      </div>

      <div
        className="p-4 rounded-xl space-y-2"
        style={{ background: "rgba(100,116,139,0.06)", border: "1px solid rgba(100,116,139,0.15)" }}
      >
        <p className="text-sm font-semibold text-white">Email Notifications</p>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Email notification delivery is not yet implemented. All critical alerts are available in-app.
        </p>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("profile");

  return (
    <motion.div variants={cv} initial="hidden" animate="show" className="space-y-6 max-w-5xl mx-auto">
      <motion.div variants={iv}>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
          Manage your account, organisation, and preferences
        </p>
      </motion.div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar nav */}
        <motion.div variants={iv} className="w-full lg:w-56 flex-shrink-0">
          <div className="card p-2 space-y-1">
            {TABS.map(tab => (
              <button
                key={tab.id}
                id={`settings-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${activeTab === tab.id ? "text-blue-400" : "text-slate-400 hover:text-white"}`}
                style={activeTab === tab.id ? { background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.15)" } : {}}
              >
                <tab.icon size={15} />
                {tab.label}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Content */}
        <motion.div variants={iv} className="flex-1">
          <div className="card overflow-hidden" style={{ minHeight: 420 }}>
            {activeTab === "profile" && <ProfileTab />}
            {activeTab === "organisation" && <OrganisationTab />}
            {activeTab === "notifications" && <NotificationsTab />}
            {activeTab === "billing" && <BillingTab />}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
