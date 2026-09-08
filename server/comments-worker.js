// The build replaces the marker with canonical article URLs, including translation pairs.
const THREADS = new Set(/* COMMENT_THREADS */ []);
const enc = new TextEncoder();
const json = (body, status = 200, headers = {}) => new Response(JSON.stringify(body), {
  status, headers: {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', ...headers}
});
const validToken = t => typeof t === 'string' && /^[a-f0-9]{64}$/.test(t);
async function digest(value) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(value))), b=>b.toString(16).padStart(2,'0')).join('');
}
async function rateKey(ip, secret, hour) {
  const key = await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode(`${hour}:${ip}`))),b=>b.toString(16).padStart(2,'0')).join('');
}
async function readBody(request) {
  if (!(request.headers.get('content-type') || '').startsWith('application/json')) throw new Error('invalid');
  const reader = request.body?.getReader();
  if (!reader) throw new Error('invalid');
  let size = 0, chunks = [];
  while (true) {
    const {value,done} = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 16000) { await reader.cancel(); throw new Error('invalid'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk,offset); offset += chunk.length; }
  const data = JSON.parse(new TextDecoder().decode(bytes));
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('invalid');
  return data;
}
async function handle(request, env) {
  const url = new URL(request.url);
  if (url.pathname !== '/api/comments') return env.ASSETS.fetch(request);
  if (!['GET','POST','DELETE'].includes(request.method)) return json({error:'method'},405,{Allow:'GET, POST, DELETE'});
  if (!env.COMMENTS_DB || !env.TURNSTILE_SITE_KEY || !env.TURNSTILE_SECRET_KEY || !env.COMMENTS_RATE_SECRET) return json({error:'unavailable'},503);
  const db = env.COMMENTS_DB;
  if (request.method === 'GET') {
    const thread = url.searchParams.get('thread');
    if (!THREADS.has(thread)) return json({error:'thread'},404);
    const cursor = url.searchParams.get('before');
    if (cursor !== null && !/^[1-9]\d{0,14}$/.test(cursor)) return json({error:'invalid'},400);
    const {results} = await db.prepare('SELECT id,name,body,created_at FROM comments WHERE thread=? AND status=\'published\' AND id < ? ORDER BY id DESC LIMIT 21')
      .bind(thread,cursor ? Number(cursor) : Number.MAX_SAFE_INTEGER).all();
    return json({comments:results.slice(0,20),next:results.length>20 ? results[19].id : null,siteKey:env.TURNSTILE_SITE_KEY});
  }
  if (request.headers.get('origin') !== url.origin) return json({error:'origin'},403);
  let data;
  try { data = await readBody(request); } catch { return json({error:'invalid'},400); }
  if (!THREADS.has(data.thread)) return json({error:'thread'},404);
  if (!validToken(data.deleteToken)) return json({error:'invalid'},400);
  const deleteHash = await digest(data.deleteToken);
  if (request.method === 'DELETE') {
    if (!Number.isSafeInteger(data.id) || data.id < 1) return json({error:'invalid'},400);
    const result = await db.prepare('DELETE FROM comments WHERE id=? AND thread=? AND delete_hash=?').bind(data.id,data.thread,deleteHash).run();
    return result.meta.changes ? json({ok:true}) : json({error:'not_found'},404);
  }
  const name = typeof data.name === 'string' ? data.name.trim() : '';
  const body = typeof data.body === 'string' ? data.body.trim() : '';
  if (!name || name.length>40 || !body || body.length>2000 || data.website || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(name+body)) return json({error:'invalid'},400);
  // The client retains this random token across network retries to avoid duplicate posts.
  const prior = await db.prepare('SELECT id,thread,name,body,created_at,status FROM comments WHERE delete_hash=?').bind(deleteHash).first();
  if (prior) return prior.thread===data.thread && prior.name===name && prior.body===body && prior.status==='published'
    ? json({comment:{id:prior.id,name:prior.name,body:prior.body,created_at:prior.created_at}})
    : json({error:'conflict'},409);
  if (typeof data.challenge !== 'string' || !data.challenge || data.challenge.length>2048) return json({error:'challenge'},403);
  let verification;
  try {
    const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({secret:env.TURNSTILE_SECRET_KEY,response:data.challenge}),signal:AbortSignal.timeout(8000)
    });
    verification = await res.json();
  } catch { return json({error:'unavailable'},503); }
  if (!verification.success || verification.hostname!==url.hostname || verification.action!=='comment') return json({error:'challenge'},403);
  const ip = request.headers.get('CF-Connecting-IP');
  if (!ip) return json({error:'unavailable'},503);
  const now = Math.floor(Date.now()/1000);
  const bucket = await rateKey(ip,env.COMMENTS_RATE_SECRET,Math.floor(now/3600));
  // This conditional upsert is atomic; simultaneous requests cannot bypass the limit.
  const limit = await db.prepare('INSERT INTO comment_limits(bucket,count,last_at,expires_at) VALUES(?,1,?,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1,last_at=excluded.last_at WHERE count<5 AND last_at<=?')
    .bind(bucket,now,now+86400,now-30).run();
  if (!limit.meta.changes) return json({error:'rate'},429,{'Retry-After':'60'});
  await db.prepare('DELETE FROM comment_limits WHERE expires_at < ?').bind(now).run();
  const comment = await db.prepare('INSERT INTO comments(thread,name,body,created_at,delete_hash) VALUES(?,?,?,?,?) RETURNING id,name,body,created_at')
    .bind(data.thread,name,body,now,deleteHash).first();
  return json({comment},201);
}
export default {
  async fetch(request,env) {
    try { return await handle(request,env); }
    catch { return json({error:'unavailable'},503); }
  }
};
