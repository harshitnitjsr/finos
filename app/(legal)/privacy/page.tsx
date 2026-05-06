import React from "react";

export const metadata = {
  title: "Privacy Policy | Orqentra",
  description: "Privacy Policy for Orqentra Financial OS.",
};

export default function PrivacyPolicy() {
  return (
    <div className="prose prose-invert max-w-none">
      <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-xl bg-white/5 border border-white/10 text-white/40 text-[10px] font-black uppercase tracking-widest mb-8">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Legal Document
      </div>
      
      <h1 className="text-4xl md:text-5xl font-black tracking-tighter mb-12 uppercase text-white">
        Privacy <span className="text-emerald-500">Policy</span>
      </h1>

      <div className="space-y-8 text-white/70 font-medium leading-relaxed">
        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">1. Introduction</h2>
          <p>
            Welcome to Orqentra. We are committed to protecting your personal information and your right to privacy. 
            If you have any questions or concerns about this privacy notice, or our practices with regards to your personal information, 
            please contact us.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">2. Information We Collect</h2>
          <p className="mb-4">
            We collect personal information that you voluntarily provide to us when you register on the Services, 
            express an interest in obtaining information about us or our products and Services, when you participate in activities on the Services, or otherwise when you contact us.
          </p>
          <ul className="list-disc pl-6 space-y-2 opacity-80">
            <li>Personal Information Provided by You. The personal information that we collect depends on the context of your interactions with us and the Services, the choices you make and the products and features you use.</li>
            <li>Financial Data. We may collect data necessary to process your payments if you make purchases, such as your payment instrument number and the security code associated with your payment instrument.</li>
            <li>Automated Information. We automatically collect certain information when you visit, use or navigate the Services. This information does not reveal your specific identity (like your name or contact information) but may include device and usage information.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">3. How We Use Your Information</h2>
          <p>
            We use personal information collected via our Services for a variety of business purposes described below. 
            We process your personal information for these purposes in reliance on our legitimate business interests, 
            in order to enter into or perform a contract with you, with your consent, and/or for compliance with our legal obligations.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">4. Sharing Your Information</h2>
          <p>
            We only share information with your consent, to comply with laws, to provide you with services, to protect your rights, or to fulfill business obligations.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">5. Security</h2>
          <p>
            We have implemented appropriate technical and organizational security measures designed to protect the security of any personal information we process. However, despite our safeguards and efforts to secure your information, no electronic transmission over the Internet or information storage technology can be guaranteed to be 100% secure.
          </p>
        </section>

        <div className="pt-8 border-t border-white/10 text-sm opacity-50">
          Last updated: May 2026
        </div>
      </div>
    </div>
  );
}
