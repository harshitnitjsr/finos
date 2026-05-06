import React from "react";

export const metadata = {
  title: "Terms & Conditions | Orqentra",
  description: "Terms and Conditions for Orqentra Financial OS.",
};

export default function TermsConditions() {
  return (
    <div className="prose prose-invert max-w-none">
      <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-xl bg-white/5 border border-white/10 text-white/40 text-[10px] font-black uppercase tracking-widest mb-8">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Legal Document
      </div>
      
      <h1 className="text-4xl md:text-5xl font-black tracking-tighter mb-12 uppercase text-white">
        Terms & <span className="text-emerald-500">Conditions</span>
      </h1>

      <div className="space-y-8 text-white/70 font-medium leading-relaxed">
        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">1. Agreement to Terms</h2>
          <p>
            These Terms of Use constitute a legally binding agreement made between you, whether personally or on behalf of an entity ("you") and Orqentra ("we," "us" or "our"), concerning your access to and use of our financial operating system and related services.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">2. Intellectual Property Rights</h2>
          <p>
            Unless otherwise indicated, the Site and Services are our proprietary property and all source code, databases, functionality, software, website designs, audio, video, text, photographs, and graphics on the Site (collectively, the "Content") and the trademarks, service marks, and logos contained therein (the "Marks") are owned or controlled by us or licensed to us.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">3. User Representations</h2>
          <p className="mb-4">
            By using the Site, you represent and warrant that:
          </p>
          <ul className="list-disc pl-6 space-y-2 opacity-80">
            <li>All registration information you submit will be true, accurate, current, and complete.</li>
            <li>You will maintain the accuracy of such information and promptly update such registration information as necessary.</li>
            <li>You have the legal capacity and you agree to comply with these Terms of Use.</li>
            <li>You will not use the Site for any illegal or unauthorized purpose.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">4. Prohibited Activities</h2>
          <p>
            You may not access or use the Site for any purpose other than that for which we make the Site available. The Site may not be used in connection with any commercial endeavors except those that are specifically endorsed or approved by us.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">5. Modifications and Interruptions</h2>
          <p>
            We reserve the right to change, modify, or remove the contents of the Site at any time or for any reason at our sole discretion without notice. However, we have no obligation to update any information on our Site. We also reserve the right to modify or discontinue all or part of the Site without notice at any time.
          </p>
        </section>

        <div className="pt-8 border-t border-white/10 text-sm opacity-50">
          Last updated: May 2026
        </div>
      </div>
    </div>
  );
}
