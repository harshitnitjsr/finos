"use client";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2, Globe, Users, ChevronRight, ChevronLeft,
  Zap, CheckCircle2, Loader2, DollarSign, Calendar
} from "lucide-react";
import toast from "react-hot-toast";

const INDUSTRIES = [
  "Technology", "Finance & Banking", "Healthcare", "E-commerce",
  "Manufacturing", "Real Estate", "Education", "Consulting",
  "Media & Entertainment", "Logistics", "Other",
];

const COMPANY_SIZES = [
  { label: "Solo founder", value: "1" },
  { label: "2–10 employees", value: "2-10" },
  { label: "11–50 employees", value: "11-50" },
  { label: "51–200 employees", value: "51-200" },
  { label: "201–500 employees", value: "201-500" },
  { label: "500+ employees", value: "500+" },
];

const CURRENCIES = [
  { label: "USD — US Dollar", value: "USD" },
  { label: "EUR — Euro", value: "EUR" },
  { label: "GBP — British Pound", value: "GBP" },
  { label: "INR — Indian Rupee", value: "INR" },
  { label: "JPY — Japanese Yen", value: "JPY" },
  { label: "AUD — Australian Dollar", value: "AUD" },
  { label: "CAD — Canadian Dollar", value: "CAD" },
];

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

type Step = "org" | "details" | "preferences" | "done";

const STEPS: Step[] = ["org", "details", "preferences", "done"];

function StepIndicator({ current }: { current: Step }) {
  const labels = ["Organisation", "Details", "Preferences", "Done"];
  const idx = STEPS.indexOf(current);
  return (
    <div className="flex items-center gap-2 mb-10">
      {STEPS.map((s, i) => (
        <div key={s} className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
            i < idx
              ? "bg-indigo-500 text-white"
              : i === idx
              ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/50"
              : "bg-white/5 text-white/20 border border-white/10"
          }`}>
            {i < idx ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
          </div>
          <span className={`text-xs font-medium ${i === idx ? "text-white" : "text-white/30"}`}>
            {labels[i]}
          </span>
          {i < STEPS.length - 1 && (
            <div className={`h-px w-8 ${i < idx ? "bg-indigo-500" : "bg-white/10"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function OnboardingPage() {
  const { data: session, update } = useSession();
  const router = useRouter();
  const [step, setStep] = useState<Step>("org");
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    orgName: "",
    industry: "",
    companySize: "",
    defaultCurrency: "USD",
    fiscalYearStart: 1,
  });

  const userName = session?.user?.name?.split(" ")[0] ?? "there";

  const set = (key: keyof typeof form, val: string | number) =>
    setForm((f) => ({ ...f, [key]: val }));

  const goNext = () => {
    const idx = STEPS.indexOf(step);
    if (idx < STEPS.length - 1) setStep(STEPS[idx + 1]);
  };
  const goPrev = () => {
    const idx = STEPS.indexOf(step);
    if (idx > 0) setStep(STEPS[idx - 1]);
  };

  const handleFinish = async () => {
    if (!form.orgName.trim()) {
      toast.error("Organisation name is required");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error ?? "Failed to save organisation");
      }

      const data = await res.json();

      // Update the JWT session in-place — no sign-out required
      await update({
        orgId: data.orgId,
        orgName: data.orgName,
        onboardingComplete: true,
      });

      setStep("done");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
      setSaving(false);
    }
  };

  const slideVariants = {
    enter: { opacity: 0, x: 40 },
    center: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -40 },
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-6">
      {/* Background glow */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(ellipse at 30% 40%, rgba(79,70,229,0.12) 0%, transparent 60%), radial-gradient(ellipse at 70% 70%, rgba(124,58,237,0.08) 0%, transparent 50%)",
        }}
      />

      <div className="w-full max-w-lg relative z-10">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-black text-white">AFOS</span>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl p-8 relative overflow-hidden"
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.08)",
            backdropFilter: "blur(12px)",
          }}
        >
          <StepIndicator current={step} />

          <AnimatePresence mode="wait">
            {/* ── STEP 1: org name ── */}
            {step === "org" && (
              <motion.div
                key="org"
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.25 }}
              >
                <h2 className="text-2xl font-black text-white mb-1">
                  Hi {userName}! 👋
                </h2>
                <p className="text-white/40 mb-8">
                  Let&apos;s set up your organisation. This takes 60 seconds.
                </p>

                <label className="block mb-5">
                  <span className="block text-sm font-semibold text-white/70 mb-2">
                    Organisation name *
                  </span>
                  <input
                    id="org-name-input"
                    type="text"
                    value={form.orgName}
                    onChange={(e) => set("orgName", e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full px-4 py-3 rounded-xl text-white placeholder-white/20 outline-none transition-all"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                    onFocus={(e) =>
                      (e.target.style.borderColor = "rgba(99,102,241,0.5)")
                    }
                    onBlur={(e) =>
                      (e.target.style.borderColor = "rgba(255,255,255,0.1)")
                    }
                    autoFocus
                  />
                </label>

                <label className="block">
                  <span className="block text-sm font-semibold text-white/70 mb-2">
                    Industry
                  </span>
                  <select
                    id="industry-select"
                    value={form.industry}
                    onChange={(e) => set("industry", e.target.value)}
                    className="w-full px-4 py-3 rounded-xl text-white outline-none transition-all appearance-none"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      color: form.industry ? "#fff" : "rgba(255,255,255,0.2)",
                    }}
                  >
                    <option value="" disabled>Select industry</option>
                    {INDUSTRIES.map((ind) => (
                      <option key={ind} value={ind} style={{ background: "#0d1424", color: "#fff" }}>
                        {ind}
                      </option>
                    ))}
                  </select>
                </label>

                <button
                  id="onboarding-next-1"
                  onClick={goNext}
                  disabled={!form.orgName.trim()}
                  className="mt-8 w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}
                >
                  Continue <ChevronRight className="w-4 h-4" />
                </button>
              </motion.div>
            )}

            {/* ── STEP 2: company size ── */}
            {step === "details" && (
              <motion.div
                key="details"
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.25 }}
              >
                <h2 className="text-2xl font-black text-white mb-1">
                  Team size
                </h2>
                <p className="text-white/40 mb-8">
                  Helps us tailor your experience.
                </p>

                <div className="grid grid-cols-2 gap-3">
                  {COMPANY_SIZES.map((s) => (
                    <button
                      key={s.value}
                      id={`size-${s.value}`}
                      onClick={() => set("companySize", s.value)}
                      className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all text-left"
                      style={{
                        background:
                          form.companySize === s.value
                            ? "rgba(79,70,229,0.2)"
                            : "rgba(255,255,255,0.04)",
                        border:
                          form.companySize === s.value
                            ? "1px solid rgba(99,102,241,0.6)"
                            : "1px solid rgba(255,255,255,0.08)",
                        color:
                          form.companySize === s.value ? "#a5b4fc" : "rgba(255,255,255,0.6)",
                      }}
                    >
                      <Users
                        className="w-4 h-4 flex-shrink-0"
                        style={{
                          color:
                            form.companySize === s.value
                              ? "#818cf8"
                              : "rgba(255,255,255,0.3)",
                        }}
                      />
                      {s.label}
                    </button>
                  ))}
                </div>

                <div className="flex gap-3 mt-8">
                  <button
                    onClick={goPrev}
                    className="flex items-center gap-2 px-5 py-3 rounded-xl font-semibold text-white/50 transition-all hover:text-white"
                    style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    <ChevronLeft className="w-4 h-4" /> Back
                  </button>
                  <button
                    id="onboarding-next-2"
                    onClick={goNext}
                    className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-white transition-all"
                    style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}
                  >
                    Continue <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            )}

            {/* ── STEP 3: preferences ── */}
            {step === "preferences" && (
              <motion.div
                key="preferences"
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.25 }}
              >
                <h2 className="text-2xl font-black text-white mb-1">
                  Financial preferences
                </h2>
                <p className="text-white/40 mb-8">
                  Used for invoices, reports, and dashboards.
                </p>

                <label className="block mb-5">
                  <span className="block text-sm font-semibold text-white/70 mb-2 flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-indigo-400" />
                    Default currency
                  </span>
                  <select
                    id="currency-select"
                    value={form.defaultCurrency}
                    onChange={(e) => set("defaultCurrency", e.target.value)}
                    className="w-full px-4 py-3 rounded-xl text-white outline-none appearance-none"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c.value} value={c.value} style={{ background: "#0d1424" }}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="block text-sm font-semibold text-white/70 mb-2 flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-indigo-400" />
                    Fiscal year starts in
                  </span>
                  <select
                    id="fiscal-select"
                    value={form.fiscalYearStart}
                    onChange={(e) => set("fiscalYearStart", parseInt(e.target.value))}
                    className="w-full px-4 py-3 rounded-xl text-white outline-none appearance-none"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    {MONTHS.map((m, i) => (
                      <option key={m} value={i + 1} style={{ background: "#0d1424" }}>
                        {m}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="flex gap-3 mt-8">
                  <button
                    onClick={goPrev}
                    className="flex items-center gap-2 px-5 py-3 rounded-xl font-semibold text-white/50 transition-all hover:text-white"
                    style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    <ChevronLeft className="w-4 h-4" /> Back
                  </button>
                  <button
                    id="onboarding-finish"
                    onClick={handleFinish}
                    disabled={saving}
                    className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-60"
                    style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}
                  >
                    {saving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>Launch AFOS <ChevronRight className="w-4 h-4" /></>
                    )}
                  </button>
                </div>
              </motion.div>
            )}

            {/* ── STEP 4: done ── */}
            {step === "done" && (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, type: "spring" }}
                className="text-center py-4"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-emerald-500/30"
                >
                  <CheckCircle2 className="w-9 h-9 text-white" />
                </motion.div>
                <h2 className="text-2xl font-black text-white mb-2">
                  You&apos;re all set! 🎉
                </h2>
                <p className="text-white/40 mb-2">
                  <span className="text-indigo-400 font-semibold">{form.orgName}</span> is ready.
                </p>
                <p className="text-white/30 text-sm mb-8">
                  Your AI financial agents are spinning up…
                </p>
                <button
                  id="onboarding-go-to-dashboard"
                  onClick={() => router.push("/dashboard")}
                  className="w-full flex items-center justify-center gap-2 px-6 py-4 rounded-xl font-bold text-white text-base transition-all hover:scale-105"
                  style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}
                >
                  Open Dashboard <ChevronRight className="w-5 h-5" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
