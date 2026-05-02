import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      orgId?: string;
      orgName?: string;
      onboardingComplete?: boolean;
      role?: string;
    } & DefaultSession["user"];
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    uid?: string;
    orgId?: string;
    orgName?: string;
    onboardingComplete?: boolean;
    role?: string;
  }
}
