import NextAuth, { type DefaultSession } from "next-auth";
import type { DefaultJWT } from "next-auth/jwt";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "./auth.config";
import { generateUUID } from "@/lib/utils";

export type UserType = "guest" | "regular";

declare module "next-auth" {
  interface Session extends DefaultSession {
    user: {
      id: string;
      type: UserType;
    } & DefaultSession["user"];
  }

  interface User {
    id?: string;
    email?: string | null;
    type: UserType;
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    id: string;
    type: UserType;
  }
}

const isProduction = process.env.NODE_ENV === "production";
const cookieDomain = process.env.COOKIE_DOMAIN; // e.g. ".reilabs.ai"

export const {
  handlers: { GET, POST },
  auth,
  signIn,
  signOut,
} = NextAuth({
  ...authConfig,
  ...(isProduction && cookieDomain
    ? {
        cookies: {
          sessionToken: {
            name: "__Secure-authjs.session-token",
            options: {
              httpOnly: true,
              sameSite: "lax",
              path: "/",
              secure: true,
              domain: cookieDomain,
            },
          },
        },
      }
    : {}),
  providers: [
    Credentials({
      id: "guest",
      credentials: {},
      async authorize() {
        const guestId = generateUUID();
        const guestEmail = `guest-${Date.now()}@local`;
        return {
          id: guestId,
          email: guestEmail,
          type: "guest",
        };
      },
    }),
    Credentials({
      id: "magic-link",
      credentials: {
        token: { type: "text" },
      },
      async authorize(credentials) {
        const token = credentials?.token as string | undefined;
        if (!token) return null;

        const apiUrl = (
          process.env.API_BASE_URL ||
          process.env.NEXT_PUBLIC_API_URL ||
          ""
        ).replace(/\/+$/, "");
        if (!apiUrl) return null;

        try {
          console.error("[authorize] Calling API:", `${apiUrl}/auth/magic-link/verify`);
          const res = await fetch(`${apiUrl}/auth/magic-link/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
          });

          console.error("[authorize] API status:", res.status);
          if (!res.ok) {
            const body = await res.text().catch(() => "(unreadable)");
            console.error("[authorize] API error body:", body);
            return null;
          }

          const data = await res.json();
          console.error("[authorize] API user:", JSON.stringify(data.user));
          const user = data.user;
          if (!user?.id || !user?.email) {
            console.error("[authorize] Missing user fields");
            return null;
          }

          return {
            id: user.id,
            email: user.email,
            type: "regular" as const,
          };
        } catch (err) {
          console.error("[authorize] fetch error:", err);
          return null;
        }
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.id = user.id as string;
        token.type = user.type;
      }

      return token;
    },
    session({ session, token }) {
      if (session.user) {
        session.user.id = token.id;
        session.user.type = token.type;
      }

      return session;
    },
  },
});
