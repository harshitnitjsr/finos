/**
 * Auth layout — redirects already-authenticated users away from /auth/signin.
 * Keeps sign-in page clean (no flash of form for logged-in users).
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (session?.user) {
    // Already signed in — send to the right place
    if (!session.user.onboardingComplete) {
      redirect("/onboarding");
    }
    redirect("/dashboard");
  }

  return <>{children}</>;
}
