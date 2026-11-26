import { nowTW, CORS } from "./_mis.mjs";

export function GET() {
  return Response.json({ ok: true, time: nowTW(), host: "vercel" }, { headers: { ...CORS, "Cache-Control": "no-store" } });
}
