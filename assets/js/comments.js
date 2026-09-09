(() => {
  const root = document.querySelector('[data-comment-thread]');
  if (!root) return;
  const en = root.dataset.commentLanguage === 'en', thread = root.dataset.commentThread;
  const form = root.querySelector('form'), status = root.querySelector('.comment-status'), list = root.querySelector('.comment-list');
  const more = root.querySelector('.comment-more'), retry = root.querySelector('.comment-retry'), submit = root.querySelector('.comment-submit');
  const text = (ko,english) => en ? english : ko;
  const messages = {
    unavailable:text('댓글에 연결하지 못했어요. 잠시 후 다시 시도해주세요.','Comments are unavailable right now. Please try again shortly.'),
    invalid:text('닉네임은 40자, 댓글은 2,000자 이내로 입력해주세요.','Enter a nickname (up to 40 characters) and a comment (up to 2,000 characters).'),
    rate:text('댓글을 너무 빠르게 남기셨어요. 잠시 후 다시 시도해주세요. 한 시간에 최대 5개까지 작성할 수 있어요.','Please wait before posting again. You can post up to 5 comments per hour.'),
    challenge:text('스팸 방지 확인을 완료한 뒤 다시 시도해주세요.','Complete the spam check and try again.'),
    conflict:text('이전 댓글의 등록 상태를 확인한 뒤 다시 작성해주세요.','Refresh to check whether your earlier comment was posted, then try again.')
  };
  let own = {}, next = null, widget = null, challenge = '', siteKey = '', pending = null, busy = false;
  const storageKey = 'brothrone-comment-keys';
  try { own = JSON.parse(localStorage.getItem(storageKey) || '{}'); if (!own || Array.isArray(own) || typeof own!=='object') own={}; } catch {}
  function remember(id,token) { own[id]=token; try { localStorage.setItem(storageKey,JSON.stringify(own)); } catch {} }
  function say(message) { status.textContent=message; }
  function eligibility() { submit.disabled=busy || !challenge; }
  async function api(method='GET',data=null,before=null) {
    const url = new URL('/api/comments',location.origin); url.searchParams.set('thread',thread);
    if (before) url.searchParams.set('before',before);
    const response = await fetch(url,{method,credentials:'same-origin',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify({...data,thread}):undefined,signal:AbortSignal.timeout(15000)});
    let result; try { result=await response.json(); } catch { throw new Error('unavailable'); }
    if (!response.ok) throw new Error(result.error || 'unavailable');
    return result;
  }
  function makeComment(comment) {
    const item=document.createElement('li'); item.className='comment-item'; item.dataset.commentId=comment.id;
    const header=document.createElement('header'), name=document.createElement('span'), time=document.createElement('time'), body=document.createElement('p');
    name.className='comment-author'; name.textContent=comment.name;
    const date=new Date(comment.created_at*1000); time.dateTime=date.toISOString(); time.textContent=new Intl.DateTimeFormat(en?'en':'ko',{dateStyle:'medium',timeStyle:'short'}).format(date);
    body.className='comment-text'; body.textContent=comment.body;
    header.append(name,time); item.append(header,body);
    if (own[comment.id]) {
      const remove=document.createElement('button');remove.type='button';remove.className='comment-delete';remove.textContent=text('내 댓글 삭제','Delete mine');
      remove.addEventListener('click',async()=>{
        if (!window.confirm(text('이 댓글을 삭제할까요?','Delete this comment?'))) return;
        remove.disabled=true;
        try { await api('DELETE',{id:comment.id,deleteToken:own[comment.id]});item.remove();delete own[comment.id];try {localStorage.setItem(storageKey,JSON.stringify(own));}catch{}say(text('댓글을 삭제했어요.','Comment deleted.')); }
        catch {say(messages.unavailable);remove.disabled=false;}
      });
      header.append(remove);
    }
    if (comment.reply) {
      const reply=document.createElement('div'), badge=document.createElement('span'), content=document.createElement('p');
      reply.className='comment-operator-reply';badge.className='comment-operator-badge';
      badge.textContent=text('BROTHRONE · 운영자','BROTHRONE · Author');content.className='comment-text';content.textContent=comment.reply.body;
      reply.append(badge,content);item.append(reply);
    }
    return item;
  }
  async function load(append=false) {
    more.disabled=true;retry.hidden=true;
    try {
      const data=await api('GET',null,append?next:null);
      if (!append) list.replaceChildren();
      for (const comment of data.comments) if (!list.querySelector(`[data-comment-id="${comment.id}"]`)) list.append(makeComment(comment));
      next=data.next;more.hidden=!next;siteKey=data.siteKey;form.hidden=false;
      say(list.children.length ? text('최근 댓글부터 보여드려요.','Newest comments first.') : text('첫 번째 이야기를 남겨주세요.','Be the first to leave a note.'));
    } catch { say(messages.unavailable);retry.hidden=false; }
    finally {more.disabled=false;}
  }
  let challengeLoading=false;
  function initChallenge() {
    if (widget!==null || challengeLoading || !siteKey) return;
    challengeLoading=true;
    const render=()=>{
      try {
        widget=window.turnstile.render(root.querySelector('.comment-challenge'),{sitekey:siteKey,action:'comment',language:en?'en':'ko',theme:document.documentElement.dataset.theme==='dark'?'dark':'light',size:'flexible',
          callback:token=>{challenge=token;eligibility();},
          'expired-callback':()=>{challenge='';eligibility();},
          'error-callback':()=>{challenge='';eligibility();say(messages.challenge);retry.hidden=false;}
        });
      } catch {say(messages.challenge);retry.hidden=false;}
      finally {challengeLoading=false;}
    };
    if (window.turnstile) {render();return;}
    const script=document.createElement('script');script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';script.async=true;
    script.onload=render;script.onerror=()=>{challengeLoading=false;script.remove();say(messages.challenge);retry.hidden=false;};document.head.append(script);
  }
  form.addEventListener('focusin',initChallenge);
  form.elements.body.addEventListener('input',()=>{root.querySelector('.comment-counter').textContent=`${form.elements.body.value.length.toLocaleString(en?'en':'ko')} / 2,000`;});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(busy || !form.reportValidity())return;
    if(!challenge){say(messages.challenge);initChallenge();return;}
    const name=form.elements.name.value.trim(),body=form.elements.body.value.trim();
    if(!name || !body){say(messages.invalid);return;}
    const signature=JSON.stringify([name,body]);
    if(!pending || pending.signature!==signature)pending={signature,token:Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,'0')).join('')};
    busy=true;eligibility();say(text('댓글을 등록하고 있어요…','Posting your comment…'));
    try {
      const data=await api('POST',{name,body,deleteToken:pending.token,website:form.elements.website.value,challenge});
      remember(data.comment.id,pending.token);
      if(!list.querySelector(`[data-comment-id="${data.comment.id}"]`))list.prepend(makeComment(data.comment));
      form.elements.body.value='';root.querySelector('.comment-counter').textContent='0 / 2,000';pending=null;say(text('댓글을 남겼어요. 고맙습니다.','Your comment is posted. Thank you.'));
    } catch(error) {say(messages[error.message] || messages.unavailable);}
    finally {busy=false;challenge='';if(widget!==null)window.turnstile.reset(widget);eligibility();}
  });
  more.addEventListener('click',()=>load(true));
  retry.addEventListener('click',()=>{if(widget!==null){window.turnstile.reset(widget);challenge='';eligibility();}else if(!form.hidden)initChallenge();load();});
  if ('IntersectionObserver' in window) {
    const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();load();}},{rootMargin:'400px'});observer.observe(root);
  } else load();
})();
