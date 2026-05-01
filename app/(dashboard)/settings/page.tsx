"use client";
import { motion } from "framer-motion";
import { Settings as SettingsIcon, Shield, CreditCard, Building, Users, Bell } from "lucide-react";
import { UserProfile } from "@clerk/nextjs";

const containerVariants = { hidden:{opacity:0}, show:{opacity:1,transition:{staggerChildren:0.06}} };
const itemVariants = { hidden:{opacity:0,y:16}, show:{opacity:1,y:0,transition:{duration:0.35}} };

export default function SettingsPage() {
  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show" className="space-y-6 max-w-5xl mx-auto">
      <motion.div variants={itemVariants}>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm mt-1" style={{ color:"var(--color-text-secondary)" }}>Manage your account, organization, and AFOS configurations</p>
      </motion.div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Settings Navigation */}
        <motion.div variants={itemVariants} className="w-full lg:w-64 flex-shrink-0">
          <div className="card p-3 space-y-1">
            {[
              { id:"profile", label:"Profile & Security", icon:Shield, active:true },
              { id:"org", label:"Organization", icon:Building, active:false },
              { id:"billing", label:"Billing & Plans", icon:CreditCard, active:false },
              { id:"team", label:"Team Members", icon:Users, active:false },
              { id:"notifications", label:"Notifications", icon:Bell, active:false },
              { id:"advanced", label:"Advanced AI", icon:SettingsIcon, active:false },
            ].map(nav => (
              <button key={nav.id} className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${nav.active ? "bg-blue-500/10 text-blue-400" : "text-slate-400 hover:text-white hover:bg-slate-800"}`}>
                <nav.icon size={16} />
                {nav.label}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Settings Content */}
        <motion.div variants={itemVariants} className="flex-1">
          <div className="card overflow-hidden" style={{ minHeight:600 }}>
          {process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
          process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY !== "your_clerk_publishable_key" ? (
            <UserProfile
              appearance={{
                elements: {
                  rootBox: "w-full",
                  card: "bg-transparent shadow-none border-0 w-full",
                  headerTitle: "text-white text-xl font-bold",
                  headerSubtitle: "text-slate-400",
                  profileSectionTitle: "text-white font-semibold border-b border-slate-800 pb-2",
                  profileSectionTitleText: "text-white",
                  profileSectionPrimaryButton: "text-blue-400 hover:text-blue-300",
                  formFieldInput: "bg-slate-900 border-slate-700 text-white focus:border-blue-500 rounded-lg",
                  formButtonPrimary: "bg-blue-600 hover:bg-blue-500 font-semibold rounded-lg",
                  badge: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
                  userPreviewMainIdentifier: "text-white font-semibold",
                  userPreviewSecondaryIdentifier: "text-slate-400",
                  accordionTriggerButton: "text-white hover:bg-slate-800 rounded-lg",
                  breadcrumbsItemBox: "text-slate-400",
                  navbar: "hidden",
                  pageScrollBox: "p-6",
                },
              }}
            />
          ) : (
            <div className="p-8 space-y-4">
              <p className="text-white font-semibold text-lg">Profile & Security</p>
              <div className="p-4 rounded-xl" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
                <p className="text-amber-400 text-sm font-medium mb-1">⚠️ Clerk not configured</p>
                <p className="text-slate-400 text-xs">
                  Add your real <code className="text-blue-400">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and{" "}
                  <code className="text-blue-400">CLERK_SECRET_KEY</code> to <code className="text-slate-300">.env.local</code> to enable user profile management.
                </p>
              </div>
              <div className="space-y-3 mt-4">
                {[["Name", "Demo User"], ["Email", "demo@afos.ai"], ["Role", "Admin"], ["Organization", "Acme Technologies"]].map(([label, val]) => (
                  <div key={label} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}>
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{label}</span>
                    <span className="text-sm font-medium text-white">{val}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
