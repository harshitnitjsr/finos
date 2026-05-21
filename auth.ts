import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import PostgresAdapter from "@auth/pg-adapter";
import pool from "@/lib/db";

// Build the adapter but stub out session-table operations.
// With session: "jwt", Auth.js only needs the adapter for persisting
// users + accounts on first login. Session CRUD hits the DB unnecessarily
// and causes errors if the sessions table has strict constraints.
const adapter = {
  ...PostgresAdapter(pool),
  createSession: undefined,
  updateSession: undefined,
  deleteSession: undefined,
  getSessionAndUser: undefined,
};

export const { handlers, auth, signIn, signOut } = NextAuth({
  // Uses the pg-adapter (with session methods stubbed) to persist user +
  // account records on first Google login. JWT handles sessions from there.
  adapter,

  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
        },
      },
    }),
  ],

  // JWT keeps the proxy fast (no DB round-trip per request).
  // The adapter is still used to persist user + account records on first login.
  session: { strategy: "jwt" },

  pages: {
    signIn: "/auth/signin",
    error: "/auth/signin",
  },

  callbacks: {
    /**
     * jwt — called when a token is created or updated.
     * On first sign-in we look up the user's org profile from DB.
     * On session.update() (called from onboarding) we refresh orgId.
     */
    async jwt({ token, user, trigger, session }) {
      // First sign-in: `user` is populated from adapter
      if (user?.id) {
        token.uid = user.id; // store real UUID from users table
        // Load org profile for this user
        const { rows } = await pool.query(
          `SELECT org_id, onboarding_complete, role
           FROM user_profiles WHERE user_id = $1 LIMIT 1`,
          [user.id]
        );
        if (rows.length > 0) {
          token.orgId = rows[0].org_id as string;
          token.onboardingComplete = rows[0].onboarding_complete as boolean;
          token.role = rows[0].role as string;
        } else {
          token.orgId = undefined;
          token.onboardingComplete = false;
          token.role = "owner";
        }
      }

      // Client-side session.update() after onboarding completes
      if (trigger === "update" && session) {
        if (session.orgId) token.orgId = session.orgId;
        if (session.orgName) token.orgName = session.orgName;
        if (session.onboardingComplete !== undefined) {
          token.onboardingComplete = session.onboardingComplete;
        }
      }

      return token;
    },

    /**
     * session — shapes the session object returned to the client.
     */
    async session({ session, token }) {
      if (session.user) {
        // Use the real UUID from the users table
        session.user.id = (token.uid as string) ?? token.sub!;
        session.user.orgId = token.orgId as string | undefined;
        session.user.orgName = token.orgName as string | undefined;
        session.user.onboardingComplete = (token.onboardingComplete as boolean) ?? false;
        session.user.role = (token.role as string) ?? "owner";
      }
      return session;
    },
  },
});
