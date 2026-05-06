"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform, useSpring, useMotionValue } from "framer-motion";
import { getPlans } from "@/lib/subscriptions";
import { 
  ArrowRight, 
  BarChart3, 
  Shield, 
  Zap, 
  Cpu, 
  Globe, 
  Play,
  Activity,
  Terminal,
  Layers,
  Fingerprint,
  Bot,
  Sparkles,
  Send
} from "lucide-react";

// --- Components ---

const MagneticWrapper = ({ children }: { children: React.ReactNode }) => {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 150, damping: 15 });
  const springY = useSpring(y, { stiffness: 150, damping: 15 });

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!ref.current) return;
    const { clientX, clientY } = e;
    const { left, top, width, height } = ref.current.getBoundingClientRect();
    const centerX = left + width / 2;
    const centerY = top + height / 2;
    x.set((clientX - centerX) * 0.35);
    y.set((clientY - centerY) * 0.35);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ x: springX, y: springY }}
      className="inline-block"
    >
      {children}
    </motion.div>
  );
};

const BackgroundParticles = () => {
  const [windowSize, setWindowSize] = useState({ width: 2000, height: 1000 });

  useEffect(() => {
    setWindowSize({ width: window.innerWidth, height: window.innerHeight });
    const handleResize = () => setWindowSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      {Array.from({ length: 60 }).map((_, i) => {
        const size = Math.random() * 3 + 2;
        const color = i % 3 === 0 ? "#10b981" : i % 3 === 1 ? "#84cc16" : "#3b82f6";
        const duration = Math.random() * 20 + 10;
        const delay = Math.random() * 20;
        const left = Math.random() * 100;
        
        return (
          <motion.div
            key={i}
            className="absolute rounded-full"
            style={{
              width: size,
              height: size,
              left: `${left}%`,
              background: color,
              boxShadow: `0 0 10px ${color}`,
            }}
            initial={{ y: "110vh", opacity: 0 }}
            animate={{ 
              y: "-10vh",
              opacity: [0, 0.4, 0.4, 0]
            }}
            transition={{ 
              duration: duration,
              delay: delay,
              repeat: Infinity,
              ease: "linear"
            }}
          />
        );
      })}
    </div>
  );
};

export default function HomePage() {
  const [mounted, setMounted] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const mockupRef = useRef<HTMLDivElement>(null);
  
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.1], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.1], [1, 0.98]);

  // Mockup 3D Tilt
  const xTilt = useMotionValue(0);
  const yTilt = useMotionValue(0);
  const rotateX = useSpring(useTransform(yTilt, [-0.5, 0.5], [10, -10]));
  const rotateY = useSpring(useTransform(xTilt, [-0.5, 0.5], [-10, 10]));

  useEffect(() => {
    setMounted(true);
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
      
      if (mockupRef.current) {
        const { left, top, width, height } = mockupRef.current.getBoundingClientRect();
        const mouseX = e.clientX - left;
        const mouseY = e.clientY - top;
        xTilt.set(mouseX / width - 0.5);
        yTilt.set(mouseY / height - 0.5);
      }
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [xTilt, yTilt]);

  // Detect billing currency from backend (IP-based, respects VPN)
  const [landingCurrency, setLandingCurrency] = useState<"INR" | "USD">("INR");
  useEffect(() => {
    getPlans()
      .then((res) => setLandingCurrency(res.detected_currency))
      .catch(() => {}); // silent fail — stays INR
  }, []);

  if (!mounted) return <div className="min-h-screen bg-[#020617]" />;

  return (
    <div className="relative min-h-screen bg-[#020617] text-white selection:bg-emerald-500/30 overflow-x-hidden font-sans">
      {/* Scroll Progress Bar */}
      <motion.div 
        className="fixed top-0 left-0 right-0 h-1 bg-emerald-500 z-[100] origin-left"
        style={{ scaleX: scrollYProgress }}
      />

      {/* Noise Texture Overlay */}
      <div className="fixed inset-0 z-50 pointer-events-none noise" />

      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div 
          className="absolute inset-0 z-0 opacity-40 transition-opacity duration-300"
          style={{
            background: `radial-gradient(1000px circle at ${mousePos.x}px ${mousePos.y}px, rgba(16, 185, 129, 0.12), transparent 80%)`
          }}
        />
        <div className="absolute inset-0 bg-grid opacity-20" />
        
        {/* Animated Aurora Blobs */}
        <motion.div 
          animate={{ 
            x: [0, 100, 0],
            y: [0, 50, 0],
            scale: [1, 1.2, 1],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] rounded-full bg-emerald-600/15 blur-[120px]" 
        />
        <motion.div 
          animate={{ 
            x: [0, -80, 0],
            y: [0, 100, 0],
            scale: [1, 1.1, 1],
          }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          className="absolute bottom-[-15%] right-[-5%] w-[55%] h-[55%] rounded-full bg-lime-600/10 blur-[150px]" 
        />
        <motion.div 
          animate={{ 
            x: [0, 50, 0],
            y: [0, -100, 0],
            scale: [1, 1.3, 1],
          }}
          transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
          className="absolute top-[20%] right-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/10 blur-[130px]" 
        />
        
        <BackgroundParticles />
        
        {/* OS Scanlines */}
        <div className="absolute inset-0 z-10 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_2px,3px_100%]" />
      </div>

      {/* Global Status Ticker */}
      <div className="fixed top-0 left-0 w-full overflow-hidden whitespace-nowrap py-1.5 bg-emerald-600/10 backdrop-blur-md border-b border-white/5 z-[60]">
        <div className="inline-block animate-[shimmer_10s_linear_infinite] px-4">
          <span className="text-[10px] font-black tracking-widest uppercase opacity-60">
            [SYS_ACTV] // [GRID_ONLINE] // [EMERALD_PROTO] // [SEC_OMEGA] // [SYS_ACTV] // [GRID_ONLINE] // [EMERALD_PROTO] // [SEC_OMEGA]
          </span>
        </div>
      </div>

      {/* Navigation */}
      <motion.nav 
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className="fixed top-8 left-1/2 -translate-x-1/2 w-[92%] max-w-6xl border border-white/5 bg-[#050810]/60 backdrop-blur-2xl z-50 px-6 py-3.5 rounded-2xl shadow-2xl"
      >
        <div className="flex items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2.5 group cursor-pointer flex-shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-lime-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 group-hover:rotate-12 transition-transform duration-500">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-black tracking-tight shiny-text uppercase">Orqentra</span>
          </div>

          {/* Nav Links */}
          <div className="hidden lg:flex items-center gap-7 text-[10px] font-black tracking-wider text-white/30 uppercase whitespace-nowrap">
            <Link href="#features" className="hover:text-white transition-colors">Infrastructure</Link>
            <Link href="#pipeline" className="hover:text-white transition-colors">Autonomous</Link>
            <Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link>
            <Link href="/dashboard" className="hover:text-white text-emerald-500 transition-colors">Intelligence</Link>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4 flex-shrink-0">
            <Link href="/auth/signin" className="hidden sm:block text-[10px] font-black tracking-wider uppercase text-white/40 hover:text-white transition-colors whitespace-nowrap">Log In</Link>
            <MagneticWrapper>
              <Link 
                href="/auth/signin"
                className="px-5 py-2.5 bg-emerald-600 text-white text-[10px] font-black tracking-wider uppercase rounded-xl hover:bg-white hover:text-black transition-all duration-300 shadow-xl shadow-emerald-500/20 whitespace-nowrap"
              >
                Launch OS
              </Link>
            </MagneticWrapper>
          </div>
        </div>
      </motion.nav>

      <main className="relative z-10">
        {/* Hero Section */}
        <section className="pt-64 pb-32 px-6">
          <div className="max-w-7xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-xl bg-white/5 border border-white/10 text-white/40 text-[10px] font-black uppercase tracking-widest mb-12"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Connected to Global Financial Grid
            </motion.div>

            <motion.h1 
              style={{ opacity, scale }}
              className="text-5xl md:text-[7.5rem] font-black tracking-tight leading-[0.85] mb-12"
            >
              FINANCIAL <br />
              <span className="text-emerald-600 italic">OS.</span>
            </motion.h1>

            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              className="max-w-3xl mx-auto text-xl md:text-2xl text-white/30 font-medium mb-16 leading-relaxed"
            >
              The manual era is over. Orqentra is the world&apos;s first <strong>Financial Operating System (FOS)</strong>. 
              A unified autonomous orchestration layer that ingests, verifies, and settles every transaction with absolute precision. <br />
              <span className="text-emerald-500/60 block mt-4 font-black">
                NOT JUST A TOOL. A FULL-STACK AUTONOMOUS FINANCIAL GRID.
              </span>
            </motion.p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-8 mb-32">
              <MagneticWrapper>
                <Link 
                  href="/auth/signin"
                  className="group relative inline-flex items-center justify-center px-12 py-6 bg-white text-black text-xl font-black rounded-2xl overflow-hidden transition-transform active:scale-95 shadow-2xl"
                >
                  <span className="relative z-10 flex items-center gap-3 tracking-tighter text-emerald-900 font-black">
                    DEPLOY SYSTEM
                    <ArrowRight className="w-6 h-6 group-hover:translate-x-2 transition-transform" />
                  </span>
                </Link>
              </MagneticWrapper>
              
              <button className="flex items-center gap-4 text-white/30 hover:text-white text-sm font-black tracking-widest uppercase transition-all">
                <div className="w-14 h-14 rounded-full border border-white/10 flex items-center justify-center hover:bg-white/5 transition-colors">
                  <Play className="w-5 h-5 fill-current ml-1" />
                </div>
                View Protocol
              </button>
            </div>

            {/* 3D Dashboard Mockup */}
            <div className="perspective-[2000px]">
              <motion.div
                ref={mockupRef}
                style={{ rotateX, rotateY }}
                className="relative mx-auto max-w-6xl p-1 rounded-[3rem] bg-gradient-to-br from-emerald-500/30 via-white/5 to-transparent border border-white/10 shadow-[0_50px_100px_-20px_rgba(0,0,0,0.8)]"
              >
                <div className="bg-[#010314] rounded-[2.8rem] overflow-hidden border border-white/10 aspect-[16/10] relative group">
                  <div className="absolute inset-0 bg-emerald-600/5 group-hover:opacity-100 opacity-0 transition-opacity" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="grid grid-cols-12 w-full h-full p-12 gap-8 opacity-20">
                      <div className="col-span-3 h-full border-r border-white/5 flex flex-col gap-10">
                        <div className="w-full h-10 bg-white/10 rounded-xl" />
                        <div className="space-y-4">
                          <div className="w-3/4 h-6 bg-white/5 rounded-lg" />
                          <div className="w-full h-6 bg-white/5 rounded-lg" />
                          <div className="w-2/3 h-6 bg-white/5 rounded-lg" />
                        </div>
                      </div>
                      <div className="col-span-9 h-full flex flex-col gap-10">
                        <div className="grid grid-cols-3 gap-6">
                          <div className="h-40 bg-white/5 rounded-3xl" />
                          <div className="h-40 bg-white/5 rounded-3xl" />
                          <div className="h-40 bg-white/5 rounded-3xl" />
                        </div>
                        <div className="flex-1 w-full bg-white/5 rounded-[2.5rem]" />
                      </div>
                    </div>
                  </div>
                  {/* Floating Agent UI Element */}
                  <motion.div 
                    animate={{ y: [0, -20, 0] }}
                    transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute top-20 right-20 p-6 rounded-2xl bg-emerald-600 border border-white/20 shadow-2xl z-20 flex items-center gap-4"
                  >
                    <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
                      <Activity className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <div className="text-[10px] font-black uppercase tracking-widest text-white/50 mb-1">Agent Status</div>
                      <div className="text-sm font-black">Executing Payment $12,400.00</div>
                    </div>
                  </motion.div>
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        {/* Neural Pipeline Section */}
        <section className="py-32 px-6">
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              {[
                { step: "01", title: "Ingest", desc: "PDFs, APIs, and Webhooks are ingested into the neural stream.", icon: <Globe className="w-6 h-6" /> },
                { step: "02", title: "Verify", desc: "Autonomous agents validate against OPA compliance rules.", icon: <Shield className="w-6 h-6" /> },
                { step: "03", title: "Execute", desc: "System execution", icon: <Zap className="w-6 h-6" /> },
                { step: "04", title: "Audit", desc: "Every transaction is logged in an immutable vector ledger.", icon: <BarChart3 className="w-6 h-6" /> }
              ].map((item, i) => (
                <motion.div 
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  viewport={{ once: true }}
                  className="p-8 rounded-3xl bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 transition-colors group"
                >
                  <div className="flex items-center justify-between mb-8">
                    <div className="w-12 h-12 rounded-xl bg-emerald-600/10 flex items-center justify-center text-emerald-500 group-hover:bg-emerald-600 group-hover:text-white transition-all">
                      {item.icon}
                    </div>
                    <span className="text-3xl font-black opacity-10 italic">{item.step}</span>
                  </div>
                  <h4 className="text-xl font-black uppercase tracking-tighter mb-4">{item.title}</h4>
                  <p className="text-sm text-white/30 font-medium leading-relaxed">{item.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* FOS Definition Section */}
        <section className="py-32 px-6 bg-white/[0.01] border-y border-white/5">
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-24 items-center">
              <motion.div
                initial={{ opacity: 0, x: -50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
              >
                <h2 className="text-4xl md:text-6xl font-black tracking-tighter mb-8 uppercase">What is a <br/><span className="text-emerald-500">Financial OS?</span></h2>
                <div className="space-y-8">
                  <div className="flex gap-6">
                    <div className="w-12 h-12 rounded-xl bg-emerald-600/10 flex items-center justify-center flex-shrink-0">
                      <Layers className="text-emerald-500 w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-xl font-black uppercase mb-2">Unified Execution Layer</h4>
                      <p className="text-white/40 font-medium">Instead of siloed tools, Orqentra provides a single execution engine for invoices, expenses, and treasury.</p>
                    </div>
                  </div>
                  <div className="flex gap-6">
                    <div className="w-12 h-12 rounded-xl bg-emerald-600/10 flex items-center justify-center flex-shrink-0">
                      <Fingerprint className="text-emerald-500 w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-xl font-black uppercase mb-2">Deterministic Identity</h4>
                      <p className="text-white/40 font-medium">Every vendor, transaction, and employee is mapped within a unified identity graph for instant verification.</p>
                    </div>
                  </div>
                  <div className="flex gap-6">
                    <div className="w-12 h-12 rounded-xl bg-emerald-600/10 flex items-center justify-center flex-shrink-0">
                      <Terminal className="text-emerald-500 w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-xl font-black uppercase mb-2">Autonomous Settlement</h4>
                      <p className="text-white/40 font-medium">The OS doesn&apos;t just record data; it executes payments and reconciles accounts autonomously.</p>
                    </div>
                  </div>
                </div>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                className="relative p-8 rounded-[3rem] bg-emerald-600/10 border border-emerald-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-grid-white opacity-5" />
                <div className="relative z-10">
                  <div className="text-[10px] font-black uppercase tracking-[0.3em] text-emerald-500/60 mb-8">System Architecture</div>
                  <div className="space-y-4">
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-between">
                      <span className="text-xs font-black uppercase">Ingestion Engine</span>
                      <span className="text-[10px] text-emerald-500 font-mono">ACTIVE</span>
                    </div>
                    <div className="w-px h-8 bg-emerald-500/20 mx-auto" />
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-between">
                      <span className="text-xs font-black uppercase">Verification Swarm</span>
                      <span className="text-[10px] text-emerald-500 font-mono">RESOLVING...</span>
                    </div>
                    <div className="w-px h-8 bg-emerald-500/20 mx-auto" />
                    <div className="p-4 rounded-2xl bg-emerald-600 border border-white/20 flex items-center justify-between shadow-2xl">
                      <span className="text-xs font-black uppercase">Settlement Rail</span>
                      <span className="text-[10px] text-white font-mono">EXECUTED</span>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        {/* Features Bento */}
        <section id="features" className="py-64 px-6 relative">
          <div className="max-w-7xl mx-auto">
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8 }}
              viewport={{ once: true, margin: "-100px" }}
              className="mb-24 text-left"
            >
              <h2 className="text-6xl md:text-8xl font-black tracking-tighter mb-8 leading-[0.8]">
                ELITE PRODUCT <br />
                <span className="text-white/20">CAPABILITIES.</span>
              </h2>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-24">
              {[
                { title: "Invoice Automation", desc: "Autonomous extraction and processing of global invoices with zero manual data entry.", icon: <Sparkles className="w-6 h-6 text-emerald-500" /> },
                { title: "Expense Management", desc: "Real-time spend tracking and policy enforcement across your entire organization.", icon: <Activity className="w-6 h-6 text-emerald-500" /> },
                { title: "Treasury Control", desc: "Live cash positions and autonomous runway projections across multiple currencies.", icon: <BarChart3 className="w-6 h-6 text-emerald-500" /> },
                { title: "Approval Center", desc: "Unified task management for exception handling and human-in-the-loop verification.", icon: <Shield className="w-6 h-6 text-emerald-500" /> },
                { title: "Vendor Health", desc: "Deep analytics into vendor relationships, spend patterns, and reliability metrics.", icon: <Globe className="w-6 h-6 text-emerald-500" /> },
                { title: "Intelligent Chat", desc: "Direct interface to your financial graph through an advanced orchestration engine.", icon: <Bot className="w-6 h-6 text-emerald-500" /> },
              ].map((feat, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  viewport={{ once: true }}
                  className="p-8 rounded-[2.5rem] bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 transition-all group"
                >
                  <div className="w-12 h-12 rounded-xl bg-emerald-600/10 flex items-center justify-center mb-6 group-hover:bg-emerald-600 transition-colors">
                    <div className="group-hover:text-white transition-colors">{feat.icon}</div>
                  </div>
                  <h4 className="text-xl font-black uppercase mb-4 tracking-tighter">{feat.title}</h4>
                  <p className="text-sm text-white/30 font-medium leading-relaxed">{feat.desc}</p>
                </motion.div>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-6 md:grid-rows-2 gap-6 h-full md:h-[900px]">
              <motion.div 
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
                viewport={{ once: true }}
                whileHover={{ y: -10 }}
                className="md:col-span-3 md:row-span-2 p-12 rounded-[3.5rem] bg-gradient-to-br from-emerald-950/30 to-[#010314] border border-white/5 group relative overflow-hidden flex flex-col justify-between"
              >
                <div className="relative z-10 text-left">
                  <div className="w-16 h-16 rounded-2xl bg-emerald-600 flex items-center justify-center mb-10">
                    <Cpu className="w-8 h-8" />
                  </div>
                  <h3 className="text-5xl font-black tracking-tighter mb-8 leading-tight text-white">AUTONOMOUS<br />LEDGER EXECUTION</h3>
                  <p className="text-xl text-white/40 leading-relaxed max-w-md font-bold">Agents that resolve, verify, and settle payments with machine precision.</p>
                </div>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, x: 50 }}
                whileInView={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                viewport={{ once: true }}
                whileHover={{ y: -10 }}
                className="md:col-span-3 p-12 rounded-[3.5rem] bg-white/5 border border-white/5 flex flex-col justify-between relative overflow-hidden group"
              >
                <div className="flex items-center justify-between">
                  <Terminal className="w-12 h-12 text-lime-400" />
                  <div className="text-[10px] font-black tracking-widest text-white/20 uppercase">Module: 02.A</div>
                </div>
                <h3 className="text-3xl font-black mb-4 tracking-tighter uppercase text-left">Deterministic Cashflow</h3>
                <p className="text-[10px] text-white/20 font-black uppercase tracking-widest">Real-time burn forecasting with zero-drift accuracy.</p>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
                viewport={{ once: true }}
                whileHover={{ y: -10 }}
                className="md:col-span-2 p-10 rounded-[3.5rem] bg-white text-black flex flex-col justify-between"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-black animate-pulse" />
                  <span className="text-[10px] font-black uppercase tracking-widest opacity-40">Live Protocol</span>
                </div>
                <h3 className="text-2xl font-black uppercase tracking-tighter text-left">ZERO-CLICK INVOICING</h3>
                <p className="text-xs font-bold leading-tight opacity-60">Upload a PDF. Orqentra processes, verifies, and settles. Instantly.</p>
              </motion.div>

              <motion.div 
                whileHover={{ y: -10 }}
                className="md:col-span-1 p-10 rounded-[3.5rem] bg-emerald-600 flex flex-col items-center justify-center group"
              >
                <div className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-4">Multi-Rail</div>
                <Layers className="w-16 h-16 group-hover:rotate-90 transition-transform duration-500 mb-4" />
                <span className="text-[10px] font-black uppercase text-center leading-tight text-white/80">Payment Approval</span>
              </motion.div>
            </div>
          </div>
        </section>

        {/* Aggressive Statement Section */}
        <section className="py-80 px-6 bg-white text-black relative overflow-hidden">
          {/* Subtle White Section Patterns */}
          <div className="absolute inset-0 opacity-[0.03] pointer-events-none bg-grid-black" />
          <div className="absolute top-0 left-1/4 w-px h-full bg-black/5" />
          <div className="absolute top-0 right-1/4 w-px h-full bg-black/5" />
          
          <motion.div 
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, ease: "circOut" }}
            viewport={{ once: true }}
            className="max-w-6xl mx-auto text-center relative z-10"
          >
            <h2 className="text-6xl md:text-[8rem] font-black tracking-tighter leading-[0.8] mb-20 text-emerald-600 uppercase">
              FINANCE <br />
              <span className="text-black">AT THE</span> <br />
              SPEED OF CODE.
            </h2>
            <div className="flex flex-col items-center gap-12">
              <p className="text-2xl md:text-3xl font-black max-w-3xl opacity-50 uppercase tracking-tighter leading-tight">
                Legacy ERPs are just slow databases. Orqentra is an active execution engine for your balance sheet. 
                Eliminate manual latency and move from record-keeping to autonomous orchestration.
              </p>
              <MagneticWrapper>
                <Link 
                  href="/auth/signin"
                  className="inline-flex items-center gap-6 px-16 py-8 bg-black text-white text-3xl font-black rounded-3xl hover:scale-105 transition-transform shadow-2xl uppercase tracking-tighter"
                >
                  UPGRADE TO ORQENTRA
                  <ArrowRight className="w-10 h-10" />
                </Link>
              </MagneticWrapper>
            </div>
          </motion.div>
        </section>

        {/* AI Assistant Section */}
        <section className="py-64 px-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-emerald-600/5 blur-[120px] rounded-full translate-y-1/2 opacity-20" />
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center gap-24">
            <motion.div 
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="flex-1 text-left"
            >
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-[10px] font-black uppercase tracking-widest mb-8">
                <Bot className="w-3.5 h-3.5" />
                Intelligence Core
              </div>
              <h2 className="text-5xl md:text-7xl font-black tracking-tighter mb-8 leading-tight">
                CONVERSE WITH <br />
                <span className="text-emerald-600">YOUR CAPITAL.</span>
              </h2>
              <p className="text-xl text-white/30 font-bold mb-12 max-w-lg leading-relaxed">
                Query your entire financial graph through a single, unified interface. 
                Powered by a swarm of specialist agents that track trends, audit logs, and answer complex treasury questions in seconds.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-12">
                {[
                  { title: "Multi-Agent Swarm", desc: "Specialists for tax, burn, and risk." },
                  { title: "Historical Context", desc: "Full memory of every transaction." }
                ].map((item, i) => (
                  <div key={i} className="flex flex-col gap-2">
                    <div className="text-emerald-500 font-black uppercase text-xs tracking-widest">{item.title}</div>
                    <p className="text-sm text-white/20 font-bold">{item.desc}</p>
                  </div>
                ))}
              </div>
              <div className="relative z-20">
                <MagneticWrapper>
                  <Link 
                    href="/dashboard"
                    className="inline-flex items-center gap-3 px-10 py-5 bg-white text-black rounded-2xl font-black hover:scale-105 transition-all shadow-2xl cursor-pointer group"
                  >
                    Enter AI Core
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-2 transition-transform" />
                  </Link>
                </MagneticWrapper>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, scale: 0.9, rotateY: 20 }}
              whileInView={{ opacity: 1, scale: 1, rotateY: 0 }}
              viewport={{ once: true }}
              className="flex-1 w-full max-w-xl aspect-square bg-[#050810] rounded-[3rem] border border-white/10 p-1 relative shadow-2xl"
            >
              <div className="w-full h-full bg-[#010314] rounded-[2.8rem] overflow-hidden flex flex-col">
                <div className="p-8 border-b border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center">
                      <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-xs font-black uppercase tracking-widest text-white/40">Orqentra Assistant</span>
                  </div>
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>
                <div className="flex-1 p-8 space-y-6">
                  <div className="max-w-[80%] p-4 rounded-2xl bg-white/5 border border-white/5 text-[10px] font-bold text-white/40 italic">
                    How much was our cloud spend in April?
                  </div>
                  <div className="max-w-[90%] p-5 rounded-2xl bg-emerald-600 text-white text-xs font-bold shadow-xl">
                    Our multi-agent audit shows total spend across AWS and Vercel. 
                    This is a 12% decrease from March. Would you like a breakdown?
                  </div>
                </div>
                <div className="p-8 border-t border-white/5 flex gap-4">
                  <div className="flex-1 h-12 bg-white/5 rounded-xl border border-white/5" />
                  <div className="w-12 h-12 bg-emerald-600 rounded-xl flex items-center justify-center">
                    <Send className="w-4 h-4" />
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* â”€â”€ Pricing Section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        <section id="pricing" className="py-64 px-6 relative overflow-hidden">
          {/* ambient glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[60%] bg-emerald-600/5 blur-[180px] rounded-full pointer-events-none" />

          <div className="max-w-7xl mx-auto relative z-10">

            {/* Header */}
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
              viewport={{ once: true, margin: "-100px" }}
              className="text-center mb-24"
            >
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-xl bg-white/5 border border-white/10 text-white/40 text-[10px] font-black uppercase tracking-widest mb-10">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Transparent Pricing Protocol
              </div>
              <h2 className="text-6xl md:text-8xl font-black tracking-tighter leading-[0.85] mb-8 uppercase">
                CHOOSE YOUR <br />
                <span className="text-white/20">OPERATING TIER.</span>
              </h2>
              <p className="max-w-2xl mx-auto text-xl text-white/30 font-bold leading-relaxed">
                Start free — no credit card needed. Upgrade when you need more invoices or AI prompts.
                {landingCurrency === "USD" && (
                  <span className="text-white/20"> Prices in USD.</span>
                )}
              </p>
            </motion.div>

            {/* Cards — exact features from /pricing page */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 items-stretch">
              {[
                {
                  tier: "00",
                  slug: "free",
                  name: "Free",
                  desc: "30-day trial — 5 invoices & 10 AI prompts.",
                  price: "₹0",
                  period: "",
                  highlight: false,
                  accentColor: "rgba(100,116,139,0.7)",
                  gradientBg: "rgba(100,116,139,0.05)",
                  features: [
                    "5 invoice uploads — trial only",
                    "10 AI chat prompts — trial only",
                    "Expires 30 days after signup",
                    "Full platform access during trial",
                  ],
                  ctaLabel: "Free — No payment needed",
                  ctaHref: "/auth/signin",
                },
                {
                  tier: "01",
                  slug: "starter",
                  name: "Starter",
                  desc: "For small teams managing their finances.",
                  price: "₹999",
                  priceUsd: "~$12",
                  period: "/mo",
                  highlight: false,
                  accentColor: "rgba(59,130,246,0.7)",
                  gradientBg: "rgba(59,130,246,0.05)",
                  features: [
                    "100 invoice uploads / month",
                    "500 AI chat prompts / month",
                    "AI OCR invoice extraction",
                    "Duplicate detection & risk scoring",
                    "Approval workflows",
                    "Vendor & analytics dashboard",
                  ],
                  ctaLabel: "Get Started",
                  ctaHref: "/auth/signin",
                },
                {
                  tier: "02",
                  slug: "pro",
                  name: "Pro",
                  desc: "For growing businesses with high invoice volume.",
                  price: "₹2,999",
                  priceUsd: "~$36",
                  period: "/mo",
                  highlight: true,
                  accentColor: "rgba(139,92,246,0.8)",
                  gradientBg: "rgba(139,92,246,0.07)",
                  features: [
                    "1,000 invoice uploads / month",
                    "5,000 AI chat prompts / month",
                    "Everything in Starter",
                    "Priority support",
                  ],
                  ctaLabel: "Get Started",
                  ctaHref: "/auth/signin",
                },
                {
                  tier: "03",
                  slug: "enterprise",
                  name: "Enterprise",
                  desc: "Unlimited everything for large organisations.",
                  price: "₹7,999",
                  priceUsd: "~$96",
                  period: "/mo",
                  highlight: false,
                  accentColor: "rgba(245,158,11,0.7)",
                  gradientBg: "rgba(245,158,11,0.05)",
                  features: [
                    "Unlimited invoice uploads",
                    "Unlimited AI chat prompts",
                    "Everything in Pro",
                  ],
                  ctaLabel: "Get Started",
                  ctaHref: "/auth/signin",
                },
              ].map((plan, i) => (
                <motion.div
                  key={plan.slug}
                  initial={{ opacity: 0, y: 40 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: i * 0.1 }}
                  viewport={{ once: true }}
                  whileHover={{ y: -8 }}
                  className="relative flex flex-col rounded-[2.5rem] overflow-hidden transition-all duration-300"
                  style={{
                    background: `linear-gradient(135deg, ${plan.gradientBg}, rgba(5,8,16,0.95))`,
                    border: `1px solid ${plan.highlight ? plan.accentColor : "rgba(255,255,255,0.05)"}`,
                    boxShadow: plan.highlight ? `0 0 60px ${plan.accentColor}20` : "none",
                  }}
                >
                  {/* Most Popular badge */}
                  {plan.highlight && (
                    <div
                      className="absolute top-0 right-0 px-3 py-1 text-[10px] font-black uppercase rounded-bl-2xl tracking-wider"
                      style={{ background: plan.accentColor, color: "#fff" }}
                    >
                      MOST POPULAR
                    </div>
                  )}

                  {/* Card header */}
                  <div className="p-8 pb-6">
                    <span className="text-5xl font-black italic leading-none mb-6 block" style={{ color: plan.accentColor, opacity: 0.15 }}>
                      {plan.tier}
                    </span>

                    <div className="text-[9px] font-black uppercase tracking-widest mb-1" style={{ color: plan.accentColor, opacity: 0.6 }}>
                      {plan.desc}
                    </div>
                    <h3 className="text-2xl font-black uppercase tracking-tighter text-white mb-6">{plan.name}</h3>

                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-black tracking-tighter text-white">
                        {/* Show INR or USD price based on backend-detected currency */}
                        {plan.slug === "free"
                          ? (landingCurrency === "INR" ? plan.price : "$0")
                          : landingCurrency === "INR"
                          ? plan.price
                          : (plan as any).priceUsd ?? plan.price
                        }
                      </span>
                      {plan.period && (
                        <span className="text-sm text-white/30 font-bold">{plan.period}</span>
                      )}
                    </div>
                    {plan.period && (
                      <p className="text-[10px] text-white/25 mt-1 font-bold">
                        Billed monthly ·{" "}
                        {landingCurrency === "INR" && (plan as any).priceUsd && (
                          <span className="text-emerald-500/50">{(plan as any).priceUsd} USD</span>
                        )}
                        {landingCurrency === "USD" && plan.slug !== "free" && (
                          <span className="text-emerald-500/50">{plan.price} INR</span>
                        )}
                      </p>
                    )}
                  </div>

                  {/* Divider */}
                  <div className="mx-8 h-px bg-white/5" />

                  {/* Features — exact copy from /pricing PLAN_FEATURES */}
                  <div className="flex-1 p-8 space-y-3">
                    {plan.features.map((feat) => (
                      <div key={feat} className="flex items-start gap-2.5">
                        <svg className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" style={{ color: plan.accentColor }}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-[12px] font-semibold text-white/55 leading-tight">{feat}</span>
                      </div>
                    ))}
                  </div>

                  {/* CTA */}
                  <div className="p-8 pt-0">
                    <Link
                      href={plan.ctaHref}
                      className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all duration-300 hover:opacity-90"
                      style={{
                        background: plan.slug === "free"
                          ? "rgba(100,116,139,0.08)"
                          : plan.accentColor + "20",
                        color: plan.slug === "free" ? "rgba(148,163,184,0.6)" : plan.accentColor,
                        border: `1px solid ${plan.slug === "free" ? "rgba(255,255,255,0.06)" : plan.accentColor + "44"}`,
                      }}
                    >
                      {plan.ctaLabel}
                      {plan.slug !== "free" && <ArrowRight className="w-3.5 h-3.5" />}
                    </Link>
                    {plan.slug !== "free" && (
                      <p className="text-center text-[10px] mt-2 text-white/20 font-bold">
                        🔒 Secure checkout ·
                      </p>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Footer note */}
            <motion.div
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              viewport={{ once: true }}
              className="mt-16 text-center space-y-2"
            >
              <p className="text-[10px] font-bold uppercase tracking-widest text-white/15">
                
              </p>
              <p className="text-[10px] font-bold text-white/15">
                We never store your card details. All transactions are encrypted end-to-end.
              </p>
            </motion.div>
          </div>
        </section>

        {/* Footer */}
        <footer className="py-32 px-6 border-t border-white/5 bg-[#010314]">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start gap-20">
            <div className="max-w-lg text-left">
               <div className="flex items-center gap-3 mb-10">
                <div className="w-12 h-12 rounded-2xl bg-emerald-600 flex items-center justify-center">
                  <Zap className="w-7 h-7 text-white" />
                </div>
                <span className="text-4xl font-black tracking-tighter uppercase text-white">Orqentra</span>
              </div>
              <p className="text-2xl text-white/20 font-black tracking-tight leading-snug">The world&apos;s first elite orchestration OS.</p>
            </div>
            
            <div className="flex gap-16">
              <div className="flex flex-col gap-4">
                <span className="text-xs font-black uppercase tracking-widest text-white/40 mb-2">Legal</span>
                <Link href="/privacy" className="text-sm font-bold text-white/20 hover:text-white transition-colors">Privacy Policy</Link>
                <Link href="/terms" className="text-sm font-bold text-white/20 hover:text-white transition-colors">Terms & Conditions</Link>
                <Link href="/refund" className="text-sm font-bold text-white/20 hover:text-white transition-colors">Refund Policy</Link>
              </div>
            </div>
          </div>
          <div className="max-w-7xl mx-auto mt-40 pt-12 border-t border-white/5 flex justify-between items-center text-[10px] font-black tracking-widest text-white/10 uppercase">
            <span>© 2026 ORQENTRA INC.</span>
            <span>CORE ORCHESTRATION PROTOCOL</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
