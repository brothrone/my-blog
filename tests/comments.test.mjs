import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import {createDatabase,loadWorker} from './comments-db.mjs';
const worker=await loadWorker();
function setup() {
 const db=createDatabase();
 return {db,env:{COMMENTS_DB:db,TURNSTILE_SITE_KEY:'public-key',TURNSTILE_SECRET_KEY:'secret-test',COMMENTS_RATE_SECRET:'rate-secret-test',ASSETS:{fetch:async()=>new Response('static')}}};
}
const token=()=>randomBytes(32).toString('hex');
const payload=(overrides={})=>({thread:'/posts/example/',name:'Traveler',body:'A helpful story. 고맙습니다.',website:'',challenge:'valid',deleteToken:token(),...overrides});
function request(method='GET',data,origin='https://brothrone.org',query='thread=%2Fposts%2Fexample%2F') {
 return new Request(`https://brothrone.org/api/comments?${query}`,{method,headers:{Origin:origin,'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.1'},body:data===undefined?undefined:JSON.stringify(data)});
}
// Tests exercise the actual SQL and handler; only the external challenge service is mocked.
const originalFetch=globalThis.fetch;
globalThis.fetch=async(url,options)=>{
 if(url!=='https://challenges.cloudflare.com/turnstile/v0/siteverify')return originalFetch(url,options);
 const input=JSON.parse(options.body);
 return Response.json({success:input.response!=='bad',hostname:input.response==='wrong-host'?'evil.example':'brothrone.org',action:input.response==='wrong-action'?'other':'comment'});
};
test('save/read round trip keeps deletion keys and IP private; retries are idempotent',async()=>{
 const {db,env}=setup(),data=payload();
 let result=await worker.fetch(request('POST',data),env);assert.equal(result.status,201);
 const {comment}=await result.json();assert.equal(comment.body,data.body);
 result=await worker.fetch(request('POST',data),env);assert.equal(result.status,200);assert.equal((await result.json()).comment.id,comment.id);
 result=await worker.fetch(request(),env);const publicData=await result.json();assert.equal(publicData.comments.length,1);
 assert.deepEqual(Object.keys(publicData.comments[0]).sort(),['body','created_at','id','name']);
 assert.equal(db.sqlite.prepare('SELECT delete_hash FROM comments').get().delete_hash.length,64);
 assert.notEqual(db.sqlite.prepare('SELECT delete_hash FROM comments').get().delete_hash,data.deleteToken);
});
test('rejects cross-origin posts, empty bodies, excessive input, honeypots and unknown threads',async()=>{
 const {env}=setup();assert.equal((await worker.fetch(request('POST',payload(),'https://evil.example'),env)).status,403);
 for(const bad of [{body:''},{body:'x'.repeat(2001)},{name:'x'.repeat(41)},{website:'spam'},{deleteToken:'short'},{body:'\u0000'}])assert.equal((await worker.fetch(request('POST',payload(bad)),env)).status,400);
 assert.equal((await worker.fetch(request('POST',payload({thread:'/fake/'})),env)).status,404);
 assert.equal((await worker.fetch(request('POST',payload({body:'x'.repeat(17000)})),env)).status,400);
 assert.equal((await worker.fetch(request('POST',null),env)).status,400);
});
test('requires valid server-side challenge, hostname and action; config fails closed',async()=>{
 const {env}=setup();
 for(const challenge of ['','bad','wrong-host','wrong-action'])assert.equal((await worker.fetch(request('POST',payload({challenge})),env)).status,403);
 assert.equal((await worker.fetch(request('POST',payload()),{...env,TURNSTILE_SECRET_KEY:undefined})).status,503);
});
test('only the author deletion key can remove a comment',async()=>{
 const {env}=setup(),data=payload();const {comment}=await(await worker.fetch(request('POST',data),env)).json();
 assert.equal((await worker.fetch(request('DELETE',{thread:data.thread,id:comment.id,deleteToken:token()}),env)).status,404);
 assert.equal((await worker.fetch(request('DELETE',{thread:data.thread,id:comment.id,deleteToken:data.deleteToken}),env)).status,200);
 assert.equal((await(await worker.fetch(request(),env)).json()).comments.length,0);
});
test('rate limit enforces spacing and hourly count with SQLite conditional upsert',async()=>{
 const {db,env}=setup();assert.equal((await worker.fetch(request('POST',payload()),env)).status,201);
 assert.equal((await worker.fetch(request('POST',payload()),env)).status,429);
 db.sqlite.exec('UPDATE comment_limits SET count=5,last_at=0');
 assert.equal((await worker.fetch(request('POST',payload()),env)).status,429);
});
test('simultaneous requests cannot both pass the spacing limit',async()=>{
 const {env}=setup();const results=await Promise.all([worker.fetch(request('POST',payload()),env),worker.fetch(request('POST',payload()),env)]);
 assert.deepEqual(results.map(r=>r.status).sort(),[201,429]);
});
test('pagination does not leak hidden comments or skip records',async()=>{
 const {db,env}=setup();const insert=db.sqlite.prepare('INSERT INTO comments(thread,name,body,created_at,delete_hash,status) VALUES(?,?,?,?,?,?)');
 for(let i=0;i<43;i++)insert.run('/posts/example/','Name',`Comment ${i}`,100+i,token(),i===10?'hidden':'published');
 const first=await(await worker.fetch(request(),env)).json();assert.equal(first.comments.length,20);assert.ok(first.next);
 const second=await(await worker.fetch(request('GET',undefined,undefined,`thread=%2Fposts%2Fexample%2F&before=${first.next}`),env)).json();
 const third=await(await worker.fetch(request('GET',undefined,undefined,`thread=%2Fposts%2Fexample%2F&before=${second.next}`),env)).json();
 const all=[...first.comments,...second.comments,...third.comments];assert.equal(new Set(all.map(c=>c.id)).size,42);assert.equal(third.next,null);assert.ok(!all.some(c=>c.body==='Comment 10'));
 assert.equal((await worker.fetch(request('GET',undefined,undefined,'thread=%2Fposts%2Fexample%2F&before=1.5'),env)).status,400);
});
test('SQL injection text is stored as data and HTML remains plain text',async()=>{
 const {db,env}=setup(),data=payload({name:"Robert'); DROP TABLE comments;--",body:'<img src=x onerror=alert(1)>'});
 const response=await worker.fetch(request('POST',data),env);assert.equal(response.status,201);assert.equal((await response.json()).comment.body,data.body);
 assert.equal(db.sqlite.prepare('SELECT count(*) AS n FROM comments').get().n,1);
});
test('static assets bypass comment configuration and unsupported methods are refused',async()=>{
 const {env}=setup();assert.equal(await(await worker.fetch(new Request('https://brothrone.org/about/'),env)).text(),'static');
 assert.equal((await worker.fetch(request('PUT',{}),env)).status,405);
});
