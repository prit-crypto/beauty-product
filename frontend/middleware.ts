import { NextResponse, type NextRequest } from "next/server";

// Optional basic auth for the hosted demo. Set DEMO_BASIC_AUTH="user:password" to turn it on.
export function middleware(req: NextRequest) {
  const creds = process.env.DEMO_BASIC_AUTH;
  if (!creds) return NextResponse.next();
  const header = req.headers.get("authorization") || "";
  const [scheme, encoded] = header.split(" ");
  if (scheme === "Basic" && encoded && atob(encoded) === creds) return NextResponse.next();
  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Dr. Beauty Care concept demo"' },
  });
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
