/**
 * Onboarding layout — server-side guard.
 * Must be signed in. Must NOT have completed onboarding already.
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (!session?.user) {
    redirect("/auth/signin");
  }

  if (session.user.onboardingComplete) {
    redirect("/dashboard");
  }

  return <>{children}</>;
}
