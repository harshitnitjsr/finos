import React from "react";

export const metadata = {
  title: "Refund Policy | Orqentra",
  description: "Refund Policy for Orqentra Financial OS.",
};

export default function RefundPolicy() {
  return (
    <div className="prose prose-invert max-w-none">
      <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-xl bg-white/5 border border-white/10 text-white/40 text-[10px] font-black uppercase tracking-widest mb-8">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Legal Document
      </div>
      
      <h1 className="text-4xl md:text-5xl font-black tracking-tighter mb-12 uppercase text-white">
        Refund <span className="text-emerald-500">Policy</span>
      </h1>

      <div className="space-y-8 text-white/70 font-medium leading-relaxed">
        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">1. Strict No-Refund Policy</h2>
          <p>
            At Orqentra, all sales and subscriptions are final. Due to the immediate access to our digital infrastructure, autonomous execution capabilities, and compute resources provided upon subscription, <strong>we do not offer any refunds, returns, or credits</strong> for any purchases or subscription charges under any circumstances.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">2. Subscription Cancellations</h2>
          <p className="mb-4">
            You can cancel your subscription at any time to prevent future charges. If you cancel your subscription:
          </p>
          <ul className="list-disc pl-6 space-y-2 opacity-80">
            <li>You will continue to have access to the platform through the end of your current paid billing period.</li>
            <li>We will not provide refunds or prorated credits for any partial-month subscription periods.</li>
            <li>No refunds will be issued for unused API credits, invoice limits, or AI prompt quotas.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">3. Billing Errors</h2>
          <p>
            In the rare event of a duplicate charge or a demonstrable billing error caused exclusively by our payment processing system, we will investigate and, at our sole discretion, issue a credit to your Orqentra account. We will not issue cash refunds or reverse charges to your bank/card unless legally obligated to do so.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-black uppercase tracking-tight text-white mb-4">4. Chargebacks</h2>
          <p>
            Initiating a chargeback or payment dispute without contacting our support team first will result in immediate suspension and potential termination of your Orqentra account and access to the Financial OS.
          </p>
        </section>

        <div className="pt-8 border-t border-white/10 text-sm opacity-50">
          Last updated: May 2026
        </div>
      </div>
    </div>
  );
}
