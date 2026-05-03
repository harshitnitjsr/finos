"use client";
import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";

const BackgroundParticles = () => {
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

export default function GlobalBackground({ showParticles = true }: { showParticles?: boolean }) {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none bg-[#020617]">
      {/* Radial Mouse Glow */}
      <div 
        className="absolute inset-0 z-0 opacity-40 transition-opacity duration-300"
        style={{
          background: `radial-gradient(1000px circle at ${mousePos.x}px ${mousePos.y}px, rgba(16, 185, 129, 0.12), transparent 80%)`
        }}
      />
      
      {/* Grid Pattern */}
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
      
      {showParticles && <BackgroundParticles />}
      
      {/* OS Scanlines */}
      <div className="absolute inset-0 z-10 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_2px,3px_100%]" />
      
      {/* Noise Texture */}
      <div className="absolute inset-0 z-50 pointer-events-none opacity-5 noise" />
    </div>
  );
}
