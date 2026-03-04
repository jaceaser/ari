import { type NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import { guestRegex, isDevelopmentEnvironment } from "./lib/constants";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  /*
   * Playwright starts the dev server and requires a 200 status to
   * begin the tests, so this ensures that the tests can start
   */
  if (pathname.startsWith("/ping")) {
    return new Response("pong", { status: 200 });
  }

  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET,
    secureCookie: !isDevelopmentEnvironment,
  });

  if (!token) {
    const forwardedHost = request.headers.get("x-forwarded-host") || request.headers.get("host");
    const forwardedProto = request.headers.get("x-forwarded-proto") || "https";
    const baseUrl = forwardedHost
      ? `${forwardedProto}://${forwardedHost}`
      : request.url;

    if (isDevelopmentEnvironment) {
      // Dev only: auto-create a guest session so unauthenticated users can browse
      const externalUrl = `${baseUrl}${request.nextUrl.pathname}${request.nextUrl.search}`;
      const redirectUrl = encodeURIComponent(externalUrl);
      return NextResponse.redirect(
        new URL(`/api/auth/guest?redirectUrl=${redirectUrl}`, baseUrl)
      );
    }

    // Production: redirect to /login unless already on a public auth page
    const publicPaths = ["/login", "/register"];
    const isPublicPath =
      publicPaths.includes(pathname) || pathname.startsWith("/verify");
    if (!isPublicPath) {
      return NextResponse.redirect(new URL("/login", baseUrl));
    }
  }

  const isGuest = guestRegex.test(token?.email ?? "");

  if (token && !isGuest && ["/login", "/register"].includes(pathname)) {
    const fwdHost = request.headers.get("x-forwarded-host") || request.headers.get("host");
    const fwdProto = request.headers.get("x-forwarded-proto") || "https";
    const base = fwdHost ? `${fwdProto}://${fwdHost}` : request.url;
    return NextResponse.redirect(new URL("/", base));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/",
    "/chat/:id",
    "/api/:path*",
    "/login",
    "/register",

    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
