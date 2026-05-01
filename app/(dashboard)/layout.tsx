import DashboardLayout from "@/components/layout/DashboardLayout";

export default function Layout({ children }: { children: React.ReactNode }) {
  // Auth check is bypassed in demo mode (no Clerk keys configured)
  // Add Clerk auth here when real keys are in .env.local
  return <DashboardLayout>{children}</DashboardLayout>;
}
