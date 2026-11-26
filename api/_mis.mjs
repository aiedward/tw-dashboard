// 證交所 MIS 盤中即時報價（與 backend/fetch_twse.py realtime()、backend/live_server.py _taiex() 同邏輯）
const MIS = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp";
const UA = "Mozilla/5.0 (tw-dashboard)";

// '1,234.5' → 1234.5；'-'、''、'X'、0 → null（與 Python num() 一致，0 視為無成交價）
export function num(s) {
  if (s === null || s === undefined) return null;
  const v = typeof s === "number" ? s : parseFloat(String(s).replace(/[^\d.\-]/g, ""));
  return Number.isFinite(v) ? v : null;
}
const first = (s) => num(String(s || "").split("_")[0]);

async function mis(exCh) {
  const url = `${MIS}?ex_ch=${encodeURIComponent(exCh)}&json=1&delay=0&_=${Date.now()}`;
  for (let i = 0; i < 2; i++) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": UA, Referer: "https://mis.twse.com.tw/stock/index.jsp" }, signal: AbortSignal.timeout(8000) });
      if (!r.ok) throw new Error(`MIS ${r.status}`);
      return (await r.json()).msgArray || [];
    } catch (e) {
      if (i === 1) throw e;
      await new Promise((res) => setTimeout(res, 600));
    }
  }
}

export async function taiex() {
  try {
    const m = (await mis("tse_t00.tw"))[0];
    const z = num(m?.z), y = num(m?.y);
    return { price: z, prev: y, chg_pct: z && y ? (z / y - 1) * 100 : null, time: m?.t ?? null };
  } catch {
    return null;
  }
}

// 一次最多 50 檔；上櫃代號用 'otc_' 前綴，否則視為上市
export async function realtime(codes) {
  const out = [];
  for (let i = 0; i < codes.length; i += 50) {
    const ex = codes.slice(i, i + 50).map((c) => (c.startsWith("tse_") || c.startsWith("otc_") ? c : `tse_${c}.tw`)).join("|");
    for (const m of await mis(ex)) {
      // 成交價 z 在「近 5 秒無成交」或鎖漲跌停時為 '-' 或 0 → 依序改用最佳買價、最佳賣價、鎖價
      const h = num(m.h), l = num(m.l);
      const z = [num(m.z), first(m.b), first(m.a), h && h === l ? h : null].find((c) => c) ?? null;
      const y = num(m.y);
      out.push({ code: m.c, name: m.n, price: z, prev: y, open: num(m.o), high: h, low: l,
                 volume: num(m.v), time: m.t, date: m.d, chg_pct: z && y ? (z / y - 1) * 100 : null });
    }
  }
  return out;
}

export function nowTW() {
  return new Date().toLocaleTimeString("en-GB", { timeZone: "Asia/Taipei", hour12: false });
}

export const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET" };
