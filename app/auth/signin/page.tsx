"use client";
import { signIn } from "next-auth/react";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Zap, Shield, BarChart3, ArrowRight, Loader2 } from "lucide-react";

export default function SignInPage() {
  const [loading, setLoading] = useState(false);
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") ?? "/dashboard";

  const handleGoogleSignIn = async () => {
    setLoading(true);
    try {
      await signIn("google", { callbackUrl });
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex">
      {/* Left pane — branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-950 via-black to-purple-950" />
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "radial-gradient(ellipse at 20% 50%, #4f46e5 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, #7c3aed 0%, transparent 50%)",
          }}
        />

        {/* Animated grid */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage:
              "linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-black text-white tracking-tight">ORQENTRA</span>
          </div>
        </div>

        <div className="relative z-10 space-y-8">
          <div>
            <h1 className="text-4xl font-black text-white leading-tight mb-4">
              Your financial ops,{" "}
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400">
                fully autonomous.
              </span>
            </h1>
            <p className="text-white/50 text-lg leading-relaxed">
              AI agents that invoice, approve, and pay — so your team doesn't
              have to.
            </p>
          </div>

          <div className="space-y-4">
            {[
              {
                icon: <BarChart3 className="w-5 h-5 text-cyan-400" />,
                title: "Real-time Analytics",
                desc: "Instant insight into cash flow and burn rate",
              },
              {
                icon: <Shield className="w-5 h-5 text-emerald-400" />,
                title: "Automated Compliance",
                desc: "Policy enforcement with zero manual effort",
              },
              {
                icon: <Zap className="w-5 h-5 text-yellow-400" />,
                title: "AI-Powered Approvals",
                desc: "Intelligent routing with risk scoring",
              },
            ].map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 * i + 0.3 }}
                className="flex items-start gap-4 p-4 rounded-2xl"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <div className="p-2 rounded-xl" style={{ background: "rgba(255,255,255,0.06)" }}>
                  {feature.icon}
                </div>
                <div>
                  <p className="text-white font-semibold text-sm">{feature.title}</p>
                  <p className="text-white/40 text-xs mt-0.5">{feature.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="relative z-10">
          <p className="text-white/20 text-xs">© 2026 Orqentra, Inc. All rights reserved.</p>
        </div>
      </div>

      {/* Right pane — sign in */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-10 lg:hidden">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-black text-white">ORQENTRA</span>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-black text-white mb-2">Welcome back</h2>
            <p className="text-white/40">Sign in to your orchestration platform.</p>
          </div>

          {/* Google Sign-in button */}
          <motion.button
            id="google-signin-btn"
            onClick={handleGoogleSignIn}
            disabled={loading}
            whileHover={{ scale: loading ? 1 : 1.02 }}
            whileTap={{ scale: loading ? 1 : 0.98 }}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 rounded-2xl font-semibold text-base transition-all relative overflow-hidden group"
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "#fff",
            }}
          >
            {/* Hover glow */}
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />

            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
            )}
            <span className="relative z-10">
              {loading ? "Connecting..." : "Continue with Google"}
            </span>
            {!loading && <ArrowRight className="w-4 h-4 ml-auto relative z-10 opacity-40 group-hover:opacity-100 transition-opacity" />}
          </motion.button>

          <p className="mt-6 text-center text-xs text-white/20 leading-relaxed">
            By signing in, you agree to our{" "}
            <span className="text-white/40 hover:text-white/60 cursor-pointer transition-colors">
              Terms of Service
            </span>{" "}
            and{" "}
            <span className="text-white/40 hover:text-white/60 cursor-pointer transition-colors">
              Privacy Policy
            </span>
            .
          </p>
        </motion.div>
      </div>
    </div>
  );
}
