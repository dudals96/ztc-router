import json,os,subprocess,sys,time,statistics,urllib.request,concurrent.futures as cf
S=os.path.dirname(os.path.abspath(__file__))
TR={'opus55':9877,'luna':9878}
def cmd(n,ev):
    s=json.load(open(f'{S}/{n}/.claude/settings.json'))
    for g in s['hooks'][ev]:
        for h in g['hooks']:
            if 'router' in h['command'] or 'shadow' in h['command']: return h['command']
PRE={"session_id":"bench","transcript_path":"/dev/null","cwd":"/tmp/x","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls -la /Users/someone/project && echo sk-abcdefghijklmnopqrstuvwxyz0123456789","description":"list"},"tool_use_id":"t1"}
POST=dict(PRE,hook_event_name="PostToolUse",tool_response={"stdout":"","stderr":"Traceback (most recent call last):\n  File \"/Users/someone/project/a.py\", line 12, in <module>\nModuleNotFoundError: No module named 'foo'","interrupted":False,"exitCode":1})
def pct(a,p): a=sorted(a); return a[min(len(a)-1,int(round(p/100*(len(a)-1))))]
import itertools
CTR=itertools.count()
def run(n,ev,payload,env):
    payload=dict(payload,tool_use_id=f't{next(CTR)}')
    t=time.perf_counter()
    r=subprocess.run(['/bin/sh','-c',cmd(n,ev)],input=json.dumps(payload),capture_output=True,text=True,env=env,timeout=10)
    return (time.perf_counter()-t)*1000, r.stdout.strip(), r.returncode
def series(n,ev,payload,env,N,conc):
    out=[];bad=0
    with cf.ThreadPoolExecutor(conc) as ex:
        for ms,so,rc in ex.map(lambda _: run(n,ev,payload,env), range(N)):
            out.append(ms); bad+= (so!='{}' or rc!=0)
    return {"n":N,"conc":conc,"p50":round(pct(out,50),1),"p95":round(pct(out,95),1),"p99":round(pct(out,99),1),"max":round(max(out),1),"non_neutral":bad}
res={}
for n,port in TR.items():
    home=f'{S}/home-{n}'; os.makedirs(home,exist_ok=True)
    env=dict(os.environ,HOME=home,CLAUDE_PROJECT_DIR=f'{S}/{n}',PI_ROUTER_PORT=str(port),PI_ROUTER_HOME=f'{home}/.pi-router/{n}')
    r={}
    d=subprocess.Popen([sys.executable,'-u','scripts/hybrid-router-daemon.py'],cwd=f'{S}/{n}',env=env,stdout=open(f'{S}/{n}-daemon.log','w'),stderr=subprocess.STDOUT)
    for _ in range(100):
        try: urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=0.3); break
        except Exception: time.sleep(0.1)
    for ev,p in (('PreToolUse',PRE),('PostToolUse',POST)):
        series(n,ev,p,env,10,1)
        r[f'{ev}_c1']=series(n,ev,p,env,200,1)
        r[f'{ev}_c3']=series(n,ev,p,env,201,3)
    try: r['health']=urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1).read().decode()[:300]
    except Exception as e: r['health']=repr(e)
    d.terminate(); d.wait(5)
    r['absent_pre']=series(n,'PreToolUse',PRE,env,50,1)
    r['bind']=None
    raw=subprocess.run(['/bin/sh','-c',f'find {home} -type f | head -20; grep -rl "abcdefghijklmnopqrstuvwxyz0123456789" {home} || echo no-secret-leak; grep -rl "/Users/someone" {home} || echo no-abs-path'],capture_output=True,text=True).stdout
    r['raw_files']=raw
    res[n]=r
    time.sleep(1)
print(json.dumps(res,ensure_ascii=False,indent=1))
