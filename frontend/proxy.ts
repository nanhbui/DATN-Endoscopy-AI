import { NextRequest, NextResponse } from 'next/server';

export function proxy(request: NextRequest): NextResponse {
  const start = Date.now();
  const response = NextResponse.next();
  const duration = Date.now() - start;

  const { pathname } = request.nextUrl;
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname.match(/\.(ico|png|svg|jpg|css|js)$/)
  ) {
    return response;
  }

  console.log(
    JSON.stringify({
      ts: new Date().toISOString(),
      method: request.method,
      path: pathname,
      duration_ms: duration,
      ua: request.headers.get('user-agent')?.slice(0, 80) ?? '',
    }),
  );

  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
