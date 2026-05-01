import Link from "next/link";
import { ArrowRight, BarChart3, Shield, Zap } from "lucide-react";
import * as motion from "framer-motion/client";

export default async function HomePage() {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const isClerkConfigured =
    publishableKey && publishableKey !== "your_clerk_publishable_key";

  return (
    <div className="flex flex-col min-h-screen bg-black text-white selection:bg-indigo-500/30">
      {/* Navigation */}
      <nav className="fixed top-0 w-full border-b border-white/10 bg-black/50 backdrop-blur-md z-50">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400">
              Finos
            </span>
          </div>
          <div className="flex gap-4">
            <Link
              href={isClerkConfigured ? "/sign-in" : "/dashboard"}
              className="px-4 py-2 text-sm font-medium text-white/70 hover:text-white transition-colors"
            >
              Log in
            </Link>
            <Link
              href={isClerkConfigured ? "/sign-up" : "/dashboard"}
              className="px-4 py-2 text-sm font-medium bg-white text-black rounded-full hover:bg-white/90 transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div
          className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur-3xl sm:-top-80"
          aria-hidden="true"
        >
          <div
            className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-[#ff80b5] to-[#9089fc] opacity-20 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]"
            style={{
              clipPath:
                "polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)",
            }}
          />
        </div>

        <div className="container mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-sm text-indigo-300 mb-8">
            <span className="flex h-2 w-2 rounded-full bg-indigo-500"></span>
            Reimagining AI-Driven Finance for Startups
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8">
            Manage your finances <br />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400">
              at the speed of light
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-xl text-white/60 mb-10">
            Finos brings intelligent agents, real-time analytics, and automated
            compliance into one beautiful platform.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href={isClerkConfigured ? "/sign-up" : "/dashboard"}
              className="flex items-center gap-2 px-8 py-4 text-base font-semibold bg-white text-black rounded-full hover:bg-gray-100 transition-all hover:scale-105"
            >
              Start for free
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-black/50 border-y border-white/10">
        <div className="container mx-auto px-6">
          <div className="grid md:grid-cols-3 gap-12">
            {[
              {
                icon: <Zap className="w-8 h-8 text-yellow-400" />,
                title: "AI-Powered Approvals",
                desc: "Our expense and compliance agents instantly review and process your financial transactions.",
              },
              {
                icon: <BarChart3 className="w-8 h-8 text-cyan-400" />,
                title: "Real-time Analytics",
                desc: "Get deep insights into your cash flow, burn rate, and run-time with beautiful charts.",
              },
              {
                icon: <Shield className="w-8 h-8 text-green-400" />,
                title: "Automated Compliance",
                desc: "Stay completely compliant with automatic categorization and policy enforcement.",
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="p-8 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
              >
                <div className="mb-6">{feature.icon}</div>
                <h3 className="text-xl font-bold mb-3">{feature.title}</h3>
                <p className="text-white/60 leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 text-center text-white/40">
        <p>© 2026 Finos, Inc. All rights reserved.</p>
      </footer>
    </div>
  );
}
