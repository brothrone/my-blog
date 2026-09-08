import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
export function createDatabase(path=':memory:') {
  const sqlite=new DatabaseSync(path); sqlite.exec(readFileSync(new URL('../server/comments-schema.sql',import.meta.url),'utf8'));
  return {sqlite,prepare(sql) {
    let args=[];
    const query={bind(...values){args=values;return query;},async first(){return sqlite.prepare(sql).get(...args) || null;},async all(){return {results:sqlite.prepare(sql).all(...args)};},async run(){const result=sqlite.prepare(sql).run(...args);return {meta:{changes:Number(result.changes)}};}};
    return query;
  }};
}
export async function loadWorker(threads=['/posts/example/']) {
  const source=readFileSync(new URL('../server/comments-worker.js',import.meta.url),'utf8').replace('/* COMMENT_THREADS */ []',JSON.stringify(threads));
  return (await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)).default;
}
