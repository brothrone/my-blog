// Local-only preview: isolated SQLite and fake verification. Never deploy this file.
import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createDatabase} from '../tests/comments-db.mjs';
const directory=resolve(process.argv[2] || '/private/tmp/brothrone-comments-build');
const worker=(await import(pathToFileURL(resolve(directory,'_worker.js')))).default;
const db=createDatabase('/private/tmp/brothrone-comments-preview.sqlite');
const env={COMMENTS_DB:db,TURNSTILE_SITE_KEY:'local-preview-key',TURNSTILE_SECRET_KEY:'local-secret',COMMENTS_RATE_SECRET:'local-rate-secret'};
const originalFetch=globalThis.fetch;
globalThis.fetch=async(url,options)=>url==='https://challenges.cloudflare.com/turnstile/v0/siteverify'
 ? Response.json({success:JSON.parse(options.body).response==='local-test-only',hostname:'127.0.0.1',action:'comment'}) : originalFetch(url,options);
const mime={'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.json':'application/json','.svg':'image/svg+xml','.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg'};
env.ASSETS={async fetch(request){
 const pathname=new URL(request.url).pathname;
 if(pathname==='/__test/turnstile.js')return new Response("window.turnstile={render(el,options){el.textContent='Local preview · simulated spam check';setTimeout(()=>options.callback('local-test-only'),50);return 'preview';},reset(){}};",{headers:{'Content-Type':'text/javascript'}});
 if(pathname==='/assets/js/comments.js')return new Response((await readFile(resolve(directory,'assets/js/comments.js'),'utf8')).replace('https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit','/__test/turnstile.js'),{headers:{'Content-Type':'text/javascript'}});
 let file=resolve(directory,'.'+decodeURIComponent(new URL(request.url).pathname));
 if(!file.startsWith(directory+sep) && file!==directory)return new Response('Not found',{status:404});
 if(file.includes('_worker.js') || file.includes('_routes.json'))return new Response('Not found',{status:404});
 try {if((await stat(file)).isDirectory())file=resolve(file,'index.html');return new Response(await readFile(file),{headers:{'Content-Type':mime[extname(file)]||'application/octet-stream'}});}
 catch{return new Response('Not found',{status:404});}
}};
http.createServer(async(req,res)=>{
 try {const chunks=[];for await(const chunk of req)chunks.push(chunk);const data=Buffer.concat(chunks);
 const headers=new Headers(req.headers);headers.set('CF-Connecting-IP','192.0.2.10');
 const response=await worker.fetch(new Request('http://127.0.0.1:4080'+req.url,{method:req.method,headers,body:['GET','HEAD'].includes(req.method)?undefined:data}),env);
 res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
 }catch{res.writeHead(500);res.end('Preview error');}
}).listen(4080,'127.0.0.1',()=>console.log('Local comments preview: http://127.0.0.1:4080'));
