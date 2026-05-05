"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Building2, CreditCard, Hash, CheckCircle, Pencil } from "lucide-react";

interface BankDetails {
  account_name?: string | null;
  account_number?: string | null;
  ifsc_code?: string | null;
}

interface VendorBankModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (details: { account_name: string; account_number: string; ifsc_code: string }) => void;
  isSubmitting?: boolean;
  existingBank?: BankDetails | null;
  vendorName?: string | null;
}

export default function VendorBankModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  existingBank,
  vendorName,
}: VendorBankModalProps) {
  const hasExisting = !!(existingBank?.account_number && existingBank?.ifsc_code);
  const [isEditing, setIsEditing] = useState(!hasExisting);

  const [accountName, setAccountName] = useState(existingBank?.account_name ?? "");
  const [accountNumber, setAccountNumber] = useState(existingBank?.account_number ?? "");
  const [ifscCode, setIfscCode] = useState(existingBank?.ifsc_code ?? "");

  // Re-sync state if the invoice changes (different vendor)
  useEffect(() => {
    setAccountName(existingBank?.account_name ?? "");
    setAccountNumber(existingBank?.account_number ?? "");
    setIfscCode(existingBank?.ifsc_code ?? "");
    setIsEditing(!hasExisting);
  }, [isOpen, existingBank?.account_number]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!accountName || !accountNumber || !ifscCode) return;
    onSubmit({ account_name: accountName, account_number: accountNumber, ifsc_code: ifscCode });
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-md overflow-hidden flex flex-col rounded-2xl"
          style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: "var(--color-border)" }}>
            <div>
              <h2 className="text-lg font-bold text-white">Vendor Bank Details</h2>
              {vendorName && (
                <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                  {vendorName}
                </p>
              )}
            </div>
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 transition-colors text-slate-400 hover:text-white">
              <X size={20} />
            </button>
          </div>

          {/* Pre-filled Read-Only View */}
          {hasExisting && !isEditing ? (
            <div className="p-5 space-y-4">
              <div className="p-4 rounded-xl space-y-3" style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)" }}>
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle size={14} className="text-emerald-400" />
                  <p className="text-xs font-semibold text-emerald-400">Bank details on file</p>
                </div>
                {[
                  { label: "Account Name", value: accountName || "—" },
                  { label: "Account Number", value: accountNumber ? `••••${accountNumber.slice(-4)}` : "—" },
                  { label: "IFSC Code", value: ifscCode || "—" },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between text-xs">
                    <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
                    <span className="text-white font-medium">{value}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => setIsEditing(true)}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-xs font-semibold transition-all hover:bg-white/5"
                style={{ color: "var(--color-text-secondary)", border: "1px solid var(--color-border)" }}
              >
                <Pencil size={12} /> Edit Bank Details
              </button>

              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all hover:bg-white/5"
                  style={{ color: "var(--color-text-secondary)", border: "1px solid var(--color-border)" }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => onSubmit({ account_name: accountName, account_number: accountNumber, ifsc_code: ifscCode })}
                  disabled={isSubmitting}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-50 text-white"
                  style={{ background: "linear-gradient(to bottom right, #10b981, #059669)" }}
                >
                  {isSubmitting ? "Processing..." : "Approve & Send Link"}
                </button>
              </div>
            </div>
          ) : (
            /* Editable Form */
            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              {hasExisting && (
                <div className="flex items-center gap-2 p-3 rounded-xl text-xs" style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.15)" }}>
                  <Pencil size={12} className="text-blue-400 flex-shrink-0" />
                  <p style={{ color: "var(--color-text-secondary)" }}>
                    Editing saved bank details. Save changes will update vendor profile.
                  </p>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">Account Holder Name</label>
                <div className="relative">
                  <Building2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={accountName}
                    onChange={e => setAccountName(e.target.value)}
                    placeholder="e.g. Acme Corp"
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm outline-none transition-all"
                    style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)", color: "var(--color-text-primary)" }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">Account Number</label>
                <div className="relative">
                  <CreditCard size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={accountNumber}
                    onChange={e => setAccountNumber(e.target.value)}
                    placeholder="e.g. 000123456789"
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm outline-none transition-all"
                    style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)", color: "var(--color-text-primary)" }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">IFSC Code</label>
                <div className="relative">
                  <Hash size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={ifscCode}
                    onChange={e => setIfscCode(e.target.value)}
                    placeholder="e.g. HDFC0000123"
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm outline-none transition-all uppercase"
                    style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)", color: "var(--color-text-primary)" }}
                  />
                </div>
              </div>

              <div className="pt-4 flex gap-3">
                <button
                  type="button"
                  onClick={hasExisting ? () => setIsEditing(false) : onClose}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all hover:bg-white/5"
                  style={{ color: "var(--color-text-secondary)", border: "1px solid var(--color-border)" }}
                >
                  {hasExisting ? "Back" : "Cancel"}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !accountName || !accountNumber || !ifscCode}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-50 text-white"
                  style={{ background: "linear-gradient(to bottom right, #3b82f6, #2563eb)" }}
                >
                  {isSubmitting ? "Processing..." : "Approve & Generate Link"}
                </button>
              </div>
            </form>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
