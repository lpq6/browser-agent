#!/usr/bin/env python3
import argparse, asyncio, base64, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

os.environ.setdefault('no_proxy', '127.0.0.1,localhost')
os.environ.setdefault('NO_PROXY', '127.0.0.1,localhost')
CDP_HTTP = os.environ.get('CDP_HTTP', os.environ.get('WIN_CHROME_CDP', 'http://127.0.0.1:9222')).rstrip('/')

# cdp_proxy.py 自动查找：优先同目录，其次环境变量指定
_SELF_DIR = Path(__file__).resolve().parent
PROXY_SCRIPT_CANDIDATES = [
    _SELF_DIR / 'cdp_proxy.py',
    Path(os.environ.get('CDP_PROXY_SCRIPT', '')) if os.environ.get('CDP_PROXY_SCRIPT') else None,
]
PROXY_SCRIPT = next((p for p in PROXY_SCRIPT_CANDIDATES if p and p.exists()), None)
LOG_PATH = Path(os.environ.get('CDP_PROXY_LOG', '/tmp/win-chrome-cdp-proxy.log'))
RISK_KEYWORDS = [
    '验证码', 'captcha', '人机', 'verify you are human', 'cloudflare',
    '风控', '风险验证', '安全验证', 'mfa', '二次验证', '2fa', 'otp',
    '支付', '付款', '充值', 'checkout', 'payment', 'pay now',
    '注册', '注册账号', 'sign up', 'create account',
    '敏感确认', '确认购买', 'confirm purchase', 'transfer', '转账',
    '绕过', 'bypass',
]

OBSERVE_JS = """
(()=>{
  const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const label = e => (e.innerText || e.value || e.getAttribute('aria-label') ||
    e.getAttribute('placeholder') || e.getAttribute('title') || e.href || '').trim();
  const body = (document.body && document.body.innerText || '').slice(0, 6000);
  const haystack = [
    body, document.title, location.href,
    ...Array.from(document.querySelectorAll('iframe')).map(f => f.src || f.title || '')
  ].join('\\n').toLowerCase();
  const riskTerms = __RISK_TERMS__;
  const riskMatches = riskTerms.filter(x => haystack.includes(String(x).toLowerCase()));
  const elements = Array.from(document.querySelectorAll(
    'a,button,input,textarea,select,[role=button],[contenteditable=true],[aria-label]'
  ))
    .filter(visible)
    .slice(0, 100)
    .map((e, i) => {
      const r = e.getBoundingClientRect();
      return {
        i, tag: e.tagName.toLowerCase(), text: label(e).slice(0, 160),
        x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
        w: Math.round(r.width), h: Math.round(r.height),
        id: e.id || '', name: e.getAttribute('name') || '',
        role: e.getAttribute('role') || '', type: e.getAttribute('type') || ''
      };
    });
  const media = Array.from(document.querySelectorAll('video,audio')).map((m, i) => {
    const hasAudio = !!(
      (m.audioTracks && m.audioTracks.length) ||
      (m.webkitAudioDecodedByteCount && m.webkitAudioDecodedByteCount > 0) ||
      m.mozHasAudio ||
      m.tagName.toLowerCase() === 'audio'
    );
    const audible = !m.paused && !m.muted && Number(m.volume) > 0 && hasAudio;
    return {
      i, tag: m.tagName.toLowerCase(), src: m.currentSrc || m.src || '',
      paused: m.paused, muted: m.muted,
      duration: Number.isFinite(m.duration) ? m.duration : null,
      currentTime: Number.isFinite(m.currentTime) ? m.currentTime : null,
      readyState: m.readyState, volume: m.volume,
      w: m.videoWidth || 0, h: m.videoHeight || 0,
      hasAudio, audible
    };
  });
  return {
    title: document.title, url: location.href, body, elements, media,
    blocked: riskMatches.length > 0, riskMatches
  };
})()
"""

def task_risk_matches(text):
    low = (text or '').lower()
    return [w for w in RISK_KEYWORDS if w.lower() in low]

def media_summary(state):
    media = state.get('media') or []
    return {
        'count': len(media),
        'has_audio': any(m.get('hasAudio') for m in media),
        'audible': any(m.get('audible') for m in media),
        'items': media,
    }

def task_report(task, state, transcript, ok=True, **extra):
    payload = {
        'ok': ok,
        'task': task,
        'result': {
            'url': state.get('url'),
            'title': state.get('title'),
            'media': media_summary(state),
            'summary': (state.get('body') or '')[:1200],
        },
        'transcript': transcript,
    }
    payload.update(extra)
    return payload

def jget(path, timeout=5):
    with urllib.request.urlopen(CDP_HTTP + path, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def ensure_cdp():
    try:
        jget('/json/version', 3); return
    except Exception:
        pass
    if PROXY_SCRIPT and PROXY_SCRIPT.exists():
        with LOG_PATH.open('ab') as log:
            subprocess.Popen([sys.executable, str(PROXY_SCRIPT)], stdout=log, stderr=log, start_new_session=True)
        for _ in range(20):
            try: jget('/json/version', 2); return
            except Exception: time.sleep(0.5)
    raise SystemExit(
        f'Windows Chrome CDP not reachable at {CDP_HTTP}.\n'
        f'1) Start Windows Chrome: chrome.exe --remote-debugging-port=9222\n'
        f'2) Start proxy: python3 cdp_proxy.py\n'
        f'Or set CDP_HTTP / CDP_PROXY_TARGET env vars.'
    )

def tabs():
    ensure_cdp()
    return [t for t in jget('/json/list') if t.get('type') == 'page']

def pick_tab(target=None):
    ts = [t for t in tabs() if not t.get('url','').startswith('devtools://') and 'DevTools - ' not in t.get('title','')]
    if target:
        matches = [t for t in ts if target in t.get('url','') or target.lower() in t.get('title','').lower()]
        if matches:
            preferred = [
                t for t in matches
                if not any(x in t.get('url','').lower() for x in ['/login', '/signin', '/auth'])
            ]
            return (preferred or matches)[-1]
    if not ts: raise SystemExit('No Chrome page tabs found')
    return ts[-1]

class PageCDP:
    def __init__(self, tab): self.tab=tab; self.ws=None; self.mid=0
    async def __aenter__(self):
        import websockets
        uri=self.tab['webSocketDebuggerUrl'].replace('localhost','127.0.0.1')
        self.ws=await websockets.connect(uri, open_timeout=10, max_size=16*1024*1024); return self
    async def __aexit__(self,*a):
        if self.ws: await self.ws.close()
    async def send(self, method, params=None, timeout=20):
        self.mid+=1; mid=self.mid
        msg={'id':mid,'method':method}
        if params is not None: msg['params']=params
        await self.ws.send(json.dumps(msg))
        while True:
            data=json.loads(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
            if data.get('id')==mid:
                if 'error' in data: raise RuntimeError(data['error'])
                return data.get('result',{})
    async def eval(self, expr, timeout=20):
        r=await self.send('Runtime.evaluate', {'expression':expr,'returnByValue':True,'awaitPromise':True,'userGesture':True}, timeout)
        obj=r.get('result',{})
        return obj.get('value', obj.get('description'))
    async def screenshot(self,path,full=False):
        await self.send('Page.enable',{})
        params={'format':'png'}
        if full:
            try:
                m=await self.send('Page.getLayoutMetrics',{})
                cs=m.get('contentSize',{})
                params['clip']={'x':0,'y':0,'width':cs.get('width',1280),'height':cs.get('height',720),'scale':1}
                params['captureBeyondViewport']=True
            except Exception: pass
        r=await self.send('Page.captureScreenshot',params,30)
        Path(path).write_bytes(base64.b64decode(r['data']))
    async def mouse_click(self,x,y,button='left'):
        await self.send('Input.dispatchMouseEvent',{'type':'mouseMoved','x':x,'y':y,'button':'none'},10)
        await self.send('Input.dispatchMouseEvent',{'type':'mousePressed','x':x,'y':y,'button':button,'clickCount':1},10)
        await self.send('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x,'y':y,'button':button,'clickCount':1},10)
    async def insert_text(self,text): await self.send('Input.insertText',{'text':text},10)
    async def key(self,key):
        await self.send('Input.dispatchKeyEvent',{'type':'keyDown','key':key,'code':key},10)
        await self.send('Input.dispatchKeyEvent',{'type':'keyUp','key':key,'code':key},10)

async def cmd_status(args):
    print(json.dumps({'ok':True,'cdp':CDP_HTTP,'pages':tabs()},ensure_ascii=False,indent=2))
async def cmd_open(args):
    ensure_cdp()
    import websockets
    info=jget('/json/version'); uri=info['webSocketDebuggerUrl'].replace('localhost','127.0.0.1')
    async with websockets.connect(uri, open_timeout=10) as ws:
        await ws.send(json.dumps({'id':1,'method':'Target.createTarget','params':{'url':args.url}}))
        resp=json.loads(await ws.recv()); tid=resp['result']['targetId']
        await ws.send(json.dumps({'id':2,'method':'Target.activateTarget','params':{'targetId':tid}}))
    await asyncio.sleep(args.wait/1000)
    print(json.dumps({'ok':True,'targetId':tid},ensure_ascii=False,indent=2))
async def cmd_snapshot(args):
    async with PageCDP(pick_tab(args.target)) as p:
        js=f"""(()=>{{const body=(document.body&&document.body.innerText||'').slice(0,{args.max_chars});const elements=Array.from(document.querySelectorAll('a,button,input,textarea,select,[role=button],[contenteditable=true]')).filter(e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)).slice(0,{args.limit}).map((e,i)=>{{const r=e.getBoundingClientRect();return {{i,tag:e.tagName.toLowerCase(),text:(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('placeholder')||e.getAttribute('title')||e.href||'').trim().slice(0,160),x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),w:Math.round(r.width),h:Math.round(r.height),id:e.id||'',name:e.getAttribute('name')||''}}}});return {{title:document.title,url:location.href,body,elements}};}})()"""
        print(json.dumps({'ok':True,**(await p.eval(js) or {})},ensure_ascii=False,indent=2))
async def cmd_find(args):
    async with PageCDP(pick_tab(args.target)) as p:
        q=json.dumps(args.query.lower())
        js=f"""(()=>Array.from(document.querySelectorAll('a,button,input,textarea,select,[role=button],[contenteditable=true],div,span')).filter(e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)).map((e,i)=>{{const txt=(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('placeholder')||e.getAttribute('title')||e.href||'').trim();const r=e.getBoundingClientRect();return {{i,tag:e.tagName.toLowerCase(),text:txt.slice(0,180),score:txt.toLowerCase().includes({q})?2:0,x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}}}}).filter(x=>x.score>0).slice(0,{args.limit}))()"""
        print(json.dumps({'ok':True,'matches':await p.eval(js)},ensure_ascii=False,indent=2))
async def cmd_click(args):
    async with PageCDP(pick_tab(args.target)) as p:
        if args.index is not None:
            js=f"(()=>{{const els=Array.from(document.querySelectorAll('a,button,input,textarea,select,[role=button],[contenteditable=true]')).filter(e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length));const e=els[{args.index}];if(!e)return null;e.scrollIntoView({{block:'center',inline:'center'}});const r=e.getBoundingClientRect();return {{x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),text:(e.innerText||e.value||'').trim().slice(0,120)}};}})()"
        elif args.selector:
            js=f"(()=>{{const e=document.querySelector({json.dumps(args.selector)});if(!e)return null;e.scrollIntoView({{block:'center',inline:'center'}});const r=e.getBoundingClientRect();return {{x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),text:(e.innerText||e.value||'').trim().slice(0,120)}};}})()"
        else:
            q=json.dumps(args.text or '')
            js=f"(()=>{{const n={q}.toLowerCase();const els=Array.from(document.querySelectorAll('a,button,input,textarea,select,[role=button]')).filter(e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length));const e=els.find(e=>(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').toLowerCase().includes(n));if(!e)return null;e.scrollIntoView({{block:'center',inline:'center'}});const r=e.getBoundingClientRect();return {{x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),text:(e.innerText||e.value||'').trim().slice(0,120)}};}})()"
        box=await p.eval(js)
        if not box: raise SystemExit('Element not found')
        await p.mouse_click(int(box['x']),int(box['y'])); await asyncio.sleep(args.after/1000)
        print(json.dumps({'ok':True,'clicked':box},ensure_ascii=False,indent=2))
async def cmd_click_xy(args):
    async with PageCDP(pick_tab(args.target)) as p:
        await p.mouse_click(args.x,args.y); print(json.dumps({'ok':True,'x':args.x,'y':args.y},ensure_ascii=False))
async def cmd_fill(args):
    async with PageCDP(pick_tab(args.target)) as p:
        js=f"(()=>{{const e=document.querySelector({json.dumps(args.selector)});if(!e)return false;e.focus();e.value={json.dumps(args.value)};e.dispatchEvent(new Event('input',{{bubbles:true}}));e.dispatchEvent(new Event('change',{{bubbles:true}}));return true;}})()"
        if not await p.eval(js): raise SystemExit('Element not found')
        print(json.dumps({'ok':True},ensure_ascii=False))
async def cmd_type(args):
    async with PageCDP(pick_tab(args.target)) as p:
        if args.selector:
            await p.eval(f"(()=>{{const e=document.querySelector({json.dumps(args.selector)}); if(e) e.focus(); return !!e;}})()")
        await p.insert_text(args.text); print(json.dumps({'ok':True},ensure_ascii=False))
async def cmd_scroll(args):
    async with PageCDP(pick_tab(args.target)) as p:
        await p.eval(f"window.scrollBy({args.x},{args.y}); true"); print(json.dumps({'ok':True},ensure_ascii=False))
async def cmd_wait(args):
    end=time.time()+args.timeout/1000
    while time.time()<end:
        async with PageCDP(pick_tab(args.target)) as p:
            ok=await p.eval(f"(document.body&&document.body.innerText||'').includes({json.dumps(args.text)})") if args.text else await p.eval(f"!!document.querySelector({json.dumps(args.selector)})")
            if ok: print(json.dumps({'ok':True},ensure_ascii=False)); return
        await asyncio.sleep(.5)
    raise SystemExit('wait timeout')
async def cmd_screenshot(args):
    async with PageCDP(pick_tab(args.target)) as p:
        await p.screenshot(args.path,args.full_page); print(json.dumps({'ok':True,'path':args.path},ensure_ascii=False))
async def cmd_media(args):
    async with PageCDP(pick_tab(args.target)) as p:
        state=await p.eval(OBSERVE_JS.replace('__RISK_TERMS__', json.dumps(RISK_KEYWORDS, ensure_ascii=False)))
        print(json.dumps({'ok':True,'media':media_summary(state)},ensure_ascii=False,indent=2))
async def cmd_report(args): await cmd_media(args)

async def cmd_task(args):
    """Safe natural-language loop: observe -> plan -> act -> verify."""
    task = args.task
    t = task.lower()
    task_risks = task_risk_matches(task)
    if task_risks:
        print(json.dumps({
            'ok': False, 'blocked': True, 'riskMatches': task_risks,
            'reason': 'Task asks for risk-sensitive, payment, account, MFA, captcha, or bypass behavior. Human takeover required.'
        }, ensure_ascii=False, indent=2))
        return

    transcript=[]
    observe_js = OBSERVE_JS.replace('__RISK_TERMS__', json.dumps(RISK_KEYWORDS, ensure_ascii=False))
    for step in range(args.steps):
        tab = pick_tab(args.target)
        async with PageCDP(tab) as p:
            try:
                state=await p.eval(observe_js, timeout=8) or {}
            except Exception as e:
                print(json.dumps({
                    'ok': False,
                    'task': task,
                    'need_human': True,
                    'reason': 'Page observation failed; target tab may be unresponsive.',
                    'error': f'{type(e).__name__}: {e}',
                    'tab': {'title': tab.get('title'), 'url': tab.get('url')},
                    'transcript': transcript,
                }, ensure_ascii=False, indent=2))
                return
            transcript.append({
                'step': step, 'phase': 'observe',
                'url': state.get('url'), 'title': state.get('title'),
                'mediaCount': len(state.get('media') or []),
            })
            if args.verbose:
                transcript[-1]['state'] = state

            if state.get('blocked'):
                shot=f'/tmp/windows-browser-agent-blocked-{int(time.time())}.png'
                await p.screenshot(shot, True)
                print(json.dumps({
                    'ok': False, 'blocked': True,
                    'riskMatches': state.get('riskMatches') or [],
                    'screenshot': shot,
                    'reason': 'Risk/captcha/MFA/payment/account confirmation UI detected. Stopped without attempting to bypass it.',
                    'state': state,
                    'transcript': transcript,
                }, ensure_ascii=False, indent=2))
                return

            plan = {'action': 'report', 'reason': 'default safe report'}
            if ('截图' in task or 'screenshot' in t):
                plan = {'action': 'screenshot', 'path': args.output}
            elif any(x in task for x in ['视频', '声音', '媒体']) or 'media' in t or 'audio' in t or 'sound' in t or 'report' in t or '检查' in task:
                plan = {'action': 'check_media'}
            elif task.startswith('打开') or t.startswith('open '):
                url = task.split(maxsplit=1)[-1] if t.startswith('open ') else task.replace('打开','',1).strip()
                plan = {'action': 'open', 'url': url}
            elif '点击' in task or 'click' in t:
                needle = task
                for prefix in ['点击', 'click']:
                    needle = needle.replace(prefix, '', 1).strip()
                plan = {'action': 'click_text', 'text': needle}
            else:
                for e in state.get('elements') or []:
                    txt = e.get('text') or ''
                    if txt and txt in task:
                        plan = {'action': 'click_text', 'text': txt}
                        break
            transcript.append({'step': step, 'phase': 'plan', **plan})

            if plan['action'] == 'screenshot':
                await p.screenshot(plan['path'], True)
                verify = await p.eval(observe_js, timeout=8) or state
                transcript.append({'step': step, 'phase': 'verify', 'ok': True})
                print(json.dumps(task_report(task, verify, transcript, True, screenshot=plan['path']), ensure_ascii=False, indent=2))
                return

            if plan['action'] == 'check_media':
                transcript.append({'step': step, 'phase': 'verify', 'ok': True, 'media': media_summary(state)})
                print(json.dumps(task_report(task, state, transcript, True), ensure_ascii=False, indent=2))
                return

            if plan['action'] == 'open':
                if not (plan['url'].startswith('http://') or plan['url'].startswith('https://')):
                    print(json.dumps(task_report(task, state, transcript, False, need_human=True, reason='Open task needs an explicit http(s) URL.'), ensure_ascii=False, indent=2))
                    return
                await cmd_open(type('A',(),{'url':plan['url'],'wait':1500})())
                transcript.append({'step': step, 'phase': 'act', 'action': 'open', 'url': plan['url']})
                continue

            if plan['action'] == 'click_text':
                needle = (plan.get('text') or '').lower()
                matches = [
                    e for e in (state.get('elements') or [])
                    if needle and needle in (e.get('text') or '').lower()
                ]
                if not matches:
                    print(json.dumps(task_report(task, state, transcript, False, need_human=True, reason='No visible text matched the click target.'), ensure_ascii=False, indent=2))
                    return
                e = matches[0]
                await p.mouse_click(int(e['x']), int(e['y']))
                await asyncio.sleep(1)
                transcript.append({'step': step, 'phase': 'act', 'action': 'click_text', 'element': e})
                verify = await p.eval(observe_js, timeout=8) or state
                if verify.get('blocked'):
                    shot=f'/tmp/windows-browser-agent-blocked-{int(time.time())}.png'
                    await p.screenshot(shot, True)
                    print(json.dumps({
                        'ok': False, 'blocked': True,
                        'riskMatches': verify.get('riskMatches') or [],
                        'screenshot': shot,
                        'reason': 'Risk/captcha/MFA/payment/account confirmation UI appeared after action. Stopped.',
                        'state': verify,
                        'transcript': transcript,
                    }, ensure_ascii=False, indent=2))
                    return
                transcript.append({'step': step, 'phase': 'verify', 'ok': True, 'url': verify.get('url')})
                print(json.dumps(task_report(task, verify, transcript, True), ensure_ascii=False, indent=2))
                return

            print(json.dumps(task_report(task, state, transcript, False, need_human=True, reason='No safe deterministic next action.'), ensure_ascii=False, indent=2))
            return
    print(json.dumps({'ok':False,'reason':'step limit reached','transcript':transcript},ensure_ascii=False,indent=2))

def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('status'); q.set_defaults(func=cmd_status)
    q=sub.add_parser('open'); q.add_argument('url'); q.add_argument('--wait',type=int,default=1500); q.set_defaults(func=cmd_open)
    q=sub.add_parser('snapshot'); q.add_argument('--target'); q.add_argument('--max-chars',type=int,default=6000); q.add_argument('--limit',type=int,default=120); q.set_defaults(func=cmd_snapshot)
    q=sub.add_parser('find'); q.add_argument('query'); q.add_argument('--target'); q.add_argument('--limit',type=int,default=30); q.set_defaults(func=cmd_find)
    q=sub.add_parser('click'); q.add_argument('text',nargs='?'); q.add_argument('--selector'); q.add_argument('--index',type=int); q.add_argument('--target'); q.add_argument('--after',type=int,default=500); q.set_defaults(func=cmd_click)
    q=sub.add_parser('click-xy'); q.add_argument('x',type=int); q.add_argument('y',type=int); q.add_argument('--target'); q.set_defaults(func=cmd_click_xy)
    q=sub.add_parser('fill'); q.add_argument('selector'); q.add_argument('value'); q.add_argument('--target'); q.set_defaults(func=cmd_fill)
    q=sub.add_parser('type'); q.add_argument('text'); q.add_argument('--selector'); q.add_argument('--target'); q.set_defaults(func=cmd_type)
    q=sub.add_parser('scroll'); q.add_argument('--x',type=int,default=0); q.add_argument('--y',type=int,default=700); q.add_argument('--target'); q.set_defaults(func=cmd_scroll)
    q=sub.add_parser('wait'); q.add_argument('--text'); q.add_argument('--selector'); q.add_argument('--target'); q.add_argument('--timeout',type=int,default=10000); q.set_defaults(func=cmd_wait)
    q=sub.add_parser('screenshot'); q.add_argument('path'); q.add_argument('--target'); q.add_argument('--full-page',action='store_true'); q.set_defaults(func=cmd_screenshot)
    q=sub.add_parser('media'); q.add_argument('--target'); q.set_defaults(func=cmd_media)
    q=sub.add_parser('report'); q.add_argument('--target'); q.set_defaults(func=cmd_report)
    q=sub.add_parser('task'); q.add_argument('task'); q.add_argument('--target'); q.add_argument('--steps',type=int,default=5); q.add_argument('--output',default='/tmp/windows-browser-agent-task.png'); q.add_argument('--verbose',action='store_true'); q.set_defaults(func=cmd_task)
    args=parser.parse_args(); asyncio.run(args.func(args))
if __name__=='__main__': main()
