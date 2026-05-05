"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Plus, Loader2, Building2, ChevronDown } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface AddExpenseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  defaultCurrency?: string;
}

interface VendorOption { id: string; name: string; category?: string; payment_currency?: string; }

export default function AddExpenseModal({ isOpen, onClose, onSuccess, defaultCurrency = "USD" }: AddExpenseModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vendors, setVendors] = useState<VendorOption[]>([]);
  const [vendorSearch, setVendorSearch] = useState("");
  const [showVendorDropdown, setShowVendorDropdown] = useState(false);
  const vendorRef = useRef<HTMLDivElement>(null);

  const [formData, setFormData] = useState({
    description: "",
    amount: "",
    currency: defaultCurrency,
    vendor_name: "",
    department: "",
    transaction_date: new Date().toISOString().split("T")[0],
  });

  // Fetch vendors when modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData(prev => ({ ...prev, currency: defaultCurrency }));
      apiFetch<{ vendors: VendorOption[] }>("/vendors/")
        .then(r => setVendors(r.vendors || []))
        .catch(() => setVendors([]));
    }
  }, [isOpen, defaultCurrency]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (vendorRef.current && !vendorRef.current.contains(e.target as Node)) {
        setShowVendorDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filteredVendors = vendors.filter(v =>
    v.name.toLowerCase().includes(vendorSearch.toLowerCase())
  ).slice(0, 8);

  const handleVendorSelect = (vendor: VendorOption) => {
    setFormData(prev => ({ ...prev, vendor_name: vendor.name }));
    setVendorSearch(vendor.name);
    setShowVendorDropdown(false);
  };

  const handleVendorInput = (val: string) => {
    setVendorSearch(val);
    setFormData(prev => ({ ...prev, vendor_name: val }));
    setShowVendorDropdown(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await apiFetch("/expenses/", {
        method: "POST",
        body: JSON.stringify({
          ...formData,
          amount: parseFloat(formData.amount),
          transaction_date: new Date(formData.transaction_date).toISOString(),
        }),
      });
      onSuccess();
      onClose();
      setVendorSearch("");
      setFormData({ description: "", amount: "", currency: defaultCurrency, vendor_name: "", department: "", transaction_date: new Date().toISOString().split("T")[0] });
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to create expense");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-2xl p-6"
              style={{
                background: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border)",
                boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
              }}
            >
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-bold text-white">Add Expense</h2>
                  <p className="text-sm text-slate-400 mt-1">AI will automatically categorize this expense.</p>
                </div>
                <button onClick={onClose} className="p-2 rounded-xl transition-colors hover:bg-white/5 text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>

              {error && (
                <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">{error}</div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Description */}
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Description</label>
                  <input
                    type="text" required value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-slate-600"
                    placeholder="e.g. Monthly AWS Hosting"
                  />
                </div>

                {/* Amount + Currency */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Amount</label>
                    <input
                      type="number" required step="0.01" min="0" value={formData.amount}
                      onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                      className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-slate-600"
                      placeholder="0.00"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Currency</label>
                    <select
                      value={formData.currency}
                      onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                      className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all"
                    >
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                      <option value="INR">INR (₹)</option>
                    </select>
                  </div>
                </div>

                {/* Vendor autocomplete + Department */}
                <div className="grid grid-cols-2 gap-4">
                  <div ref={vendorRef} className="relative">
                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Vendor</label>
                    <div className="relative">
                      <input
                        type="text" value={vendorSearch}
                        onChange={(e) => handleVendorInput(e.target.value)}
                        onFocus={() => setShowVendorDropdown(true)}
                        className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl pl-4 pr-8 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-slate-600"
                        placeholder="Search or type new…"
                      />
                      <ChevronDown size={14} className="absolute right-3 top-3 text-slate-500 pointer-events-none" />
                    </div>

                    <AnimatePresence>
                      {showVendorDropdown && (
                        <motion.div
                          initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                          className="absolute z-50 w-full mt-1 rounded-xl overflow-hidden shadow-xl"
                          style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border)" }}
                        >
                          {filteredVendors.length > 0 ? filteredVendors.map(v => (
                            <button key={v.id} type="button" onClick={() => handleVendorSelect(v)}
                              className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors">
                              <Building2 size={12} className="text-blue-400 shrink-0" />
                              <div className="min-w-0">
                                <p className="text-sm text-white truncate">{v.name}</p>
                                {v.category && <p className="text-xs text-slate-500 truncate">{v.category}</p>}
                              </div>
                            </button>
                          )) : (
                            <div className="px-3 py-2.5 text-xs text-slate-500">
                              {vendorSearch ? `↵ Create new: "${vendorSearch}"` : "Start typing to search vendors"}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Department</label>
                    <input
                      type="text" value={formData.department}
                      onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                      className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-slate-600"
                      placeholder="e.g. Engineering"
                    />
                  </div>
                </div>

                {/* Date */}
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Date</label>
                  <input
                    type="date" required value={formData.transaction_date}
                    onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
                    className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all [color-scheme:dark]"
                  />
                </div>

                <div className="pt-4 mt-6 border-t border-slate-700/50 flex items-center justify-end gap-3">
                  <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors">
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !formData.description || !formData.amount}
                    className="px-4 py-2.5 rounded-xl text-sm font-medium bg-emerald-500 hover:bg-emerald-400 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                    {isSubmitting ? "Adding..." : "Add Expense"}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
