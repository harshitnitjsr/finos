"use client";
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";
import { useState } from "react";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-all"
      style={{
        background: "rgba(255,255,255,0.08)",
        color: "var(--color-text-secondary)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {copied ? (
        <><Check size={11} className="text-emerald-400" /> Copied</>
      ) : (
        <><Copy size={11} /> Copy</>
      )}
    </button>
  );
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content ${className ?? ""}`} style={{ color: "var(--color-text-secondary)" }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // ── Code blocks ──────────────────────────────────────────────────
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const codeStr = String(children).replace(/\n$/, "");
            const isBlock = node?.position?.start.line !== node?.position?.end.line || codeStr.includes("\n");

            if (isBlock || match) {
              return (
                <div
                  className="relative rounded-xl overflow-hidden my-3"
                  style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  {/* Header bar */}
                  <div
                    className="flex items-center justify-between px-4 py-2"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      borderBottom: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    <span
                      className="text-xs font-mono font-medium"
                      style={{ color: "var(--color-text-muted)" }}
                    >
                      {match ? match[1] : "code"}
                    </span>
                    <CopyButton text={codeStr} />
                  </div>
                  <SyntaxHighlighter
                    style={oneDark}
                    language={match ? match[1] : "text"}
                    PreTag="div"
                    customStyle={{
                      margin: 0,
                      background: "rgba(0,0,0,0.4)",
                      fontSize: "13px",
                      lineHeight: "1.6",
                      padding: "16px",
                    }}
                  >
                    {codeStr}
                  </SyntaxHighlighter>
                </div>
              );
            }
            // Inline code
            return (
              <code
                className="px-1.5 py-0.5 rounded-md font-mono text-xs"
                style={{
                  background: "rgba(59,130,246,0.12)",
                  color: "#93c5fd",
                  border: "1px solid rgba(59,130,246,0.15)",
                }}
                {...props}
              >
                {children}
              </code>
            );
          },
          // ── Tables ────────────────────────────────────────────────────────
          table({ children }) {
            return (
              <div className="overflow-x-auto my-3 rounded-xl" style={{ border: "1px solid rgba(255,255,255,0.08)" }}>
                <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return (
              <thead style={{ background: "rgba(255,255,255,0.04)", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                {children}
              </thead>
            );
          },
          th({ children }) {
            return (
              <th
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td
                className="px-4 py-3 text-sm"
                style={{
                  borderTop: "1px solid rgba(255,255,255,0.04)",
                  color: "var(--color-text-secondary)",
                }}
              >
                {children}
              </td>
            );
          },
          tr({ children }) {
            return (
              <tr
                className="transition-colors"
                style={{ background: "transparent" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "rgba(255,255,255,0.02)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
              >
                {children}
              </tr>
            );
          },
          // ── Text elements ─────────────────────────────────────────────────
          p({ children }) {
            return (
              <p className="mb-3 last:mb-0 leading-relaxed text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {children}
              </p>
            );
          },
          h1({ children }) {
            return <h1 className="text-xl font-bold mb-3 mt-4" style={{ color: "var(--color-text-primary)" }}>{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="text-lg font-semibold mb-2 mt-4" style={{ color: "var(--color-text-primary)" }}>{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-base font-semibold mb-2 mt-3" style={{ color: "var(--color-text-primary)" }}>{children}</h3>;
          },
          ul({ children }) {
            return <ul className="list-disc list-inside space-y-1 mb-3 text-sm" style={{ color: "var(--color-text-secondary)" }}>{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal list-inside space-y-1 mb-3 text-sm" style={{ color: "var(--color-text-secondary)" }}>{children}</ol>;
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>;
          },
          blockquote({ children }) {
            return (
              <blockquote
                className="pl-4 py-1 my-3 text-sm italic"
                style={{
                  borderLeft: "3px solid var(--color-accent-blue)",
                  color: "var(--color-text-muted)",
                  background: "rgba(59,130,246,0.04)",
                }}
              >
                {children}
              </blockquote>
            );
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="underline transition-colors"
                style={{ color: "var(--color-accent-blue)" }}
              >
                {children}
              </a>
            );
          },
          hr() {
            return <hr className="my-4" style={{ borderColor: "var(--color-border)" }} />;
          },
          strong({ children }) {
            return <strong style={{ color: "var(--color-text-primary)", fontWeight: 600 }}>{children}</strong>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
