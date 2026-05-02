/**
 * Dashboard group layout — server-side auth guard.
 *
 * Acts as the second defence layer after the Edge middleware in proxy.ts.
 * Both must pass for a dashboard page to render. This catches any edge cases
 * that middleware might miss (e.g. prefetch requests, unusual crawlers).
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import DashboardLayout from "@/components/layout/DashboardLayout";

export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  // Not signed in
  if (!session?.user) {
    redirect("/auth/signin");
  }

  // Signed in but hasn't completed onboarding
  if (!session.user.onboardingComplete) {
    redirect("/onboarding");
  }

  // Signed in but org somehow missing (edge case: DB inconsistency)
  if (!session.user.orgId) {
    redirect("/onboarding");
  }

  return <DashboardLayout>{children}</DashboardLayout>;
}
