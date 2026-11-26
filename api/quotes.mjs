import { realtime, taiex, nowTW, CORS } from "./_mis.mjs";

// /api/quotes?codes=2330,2317,...  — 與 Colab live_server /quotes 相同格式
// CDN 快取 5 秒：所有訪客共用同一份報價，避免對證交所 MIS 發太多請求
export async function GET(request) {
  const raw = new URL(request.url).searchParams.get("codes") || "";
  if (raw.length > 2000) return Response.json({ error: "codes too long" }, { status: 400, headers: CORS });
  const codes = [...new Set(raw.split(",").filter((c) => /^\d{4,6}[A-Z]?$/.test(c)))].slice(0, 300);
  if (!codes.length) return Response.json({ error: "codes required" }, { status: 400, headers: CORS });
  try {
    const [market, quotes] = await Promise.all([taiex(), realtime(codes)]);
    return Response.json({ time: nowTW(), market, quotes }, {
      headers: { ...CORS, "Cache-Control": "public, max-age=0, s-maxage=5, stale-while-revalidate=10" },
    });
  } catch (e) {
    return Response.json({ error: String(e?.message || e) }, { status: 502, headers: { ...CORS, "Cache-Control": "no-store" } });
  }
}
