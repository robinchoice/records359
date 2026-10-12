#!/usr/bin/env python3
"""Install the Klanglabor saver and keep its display awake only while locked."""
from pathlib import Path
import copy, datetime, json, os, plistlib, re, shutil, subprocess

base = Path(__file__).resolve().parent
library = Path('~/Library').expanduser()
support = library/'Application Support/Klanglabor Screen Saver'
bundle = library/'Screen Savers/Klanglabor.saver'
agent = library/'LaunchAgents/de.359records.klanglabor.lock-display.plist'
store = library/'Application Support/com.apple.wallpaper/Store/Index.plist'
logs = base.parents[2]/'.savor-logs/klanglabor-lock-display.log'
label = 'de.359records.klanglabor.lock-display'
uid = os.getuid()

def run(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True)

support.mkdir(parents=True, exist_ok=True)
backup = support/'original-settings.plist'
data = plistlib.loads(store.read_bytes())
if not backup.exists():
    host = run('defaults','-currentHost','export','com.apple.screensaver','-',check=False)
    user = run('defaults','export','com.apple.screensaver','-',check=False)
    original = {'WallpaperStore': data,
                'HostPreferences': plistlib.loads(host.stdout) if host.returncode == 0 else {},
                'UserPreferences': plistlib.loads(user.stdout) if user.returncode == 0 else {}}
    backup.write_bytes(plistlib.dumps(original, fmt=plistlib.FMT_BINARY))

bundle.parent.mkdir(parents=True, exist_ok=True)
if bundle.exists():
    info = plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
    assert info.get('CFBundleIdentifier') == 'de.359records.klanglabor.screensaver'
shutil.copytree(base/'Klanglabor.saver', bundle, dirs_exist_ok=True)
shutil.copy2(base/'KlanglaborLockDisplay', support/'KlanglaborLockDisplay')
config = plistlib.dumps({'module': {'relative': bundle.as_uri()}},fmt=plistlib.FMT_BINARY)
now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
count = 0

def set_idle(node):
    global count
    if isinstance(node, dict):
        if isinstance(node.get('Idle'), dict):
            node['Idle'] = {'LastSet':now, 'LastUse':now,
                'Content': {'Choices':[{'Provider':'com.apple.wallpaper.choice.screen-saver',
                                       'Files':[], 'Configuration':config}], 'Shuffle':'$null'}}
            count += 1
        for key, value in node.items():
            if key != 'Idle': set_idle(value)
    elif isinstance(node, list):
        for value in node: set_idle(value)
set_idle(data)
# Desktop choices and Spaces remain as they were.
temporary = store.with_name('Index.klanglabor.tmp')
temporary.write_bytes(plistlib.dumps(data,fmt=plistlib.FMT_BINARY))
temporary.replace(store)
run('defaults','-currentHost','write','com.apple.screensaver','moduleDict','-dict',
    'moduleName','-string','Klanglabor','path','-string',str(bundle),'type','-int','0')
run('defaults','write','com.apple.screensaver','askForPassword','-int','1')
run('defaults','write','com.apple.screensaver','askForPasswordDelay','-int','0')
agent.parent.mkdir(parents=True,exist_ok=True)
logs.parent.mkdir(parents=True,exist_ok=True)
job = {'Label':label, 'ProgramArguments':[str(support/'KlanglaborLockDisplay')],
       'RunAtLoad':True,'KeepAlive':True,'LimitLoadToSessionType':'Aqua',
       'WorkingDirectory':str(base.parents[2]),
       'StandardOutPath':str(logs),'StandardErrorPath':str(logs),'ThrottleInterval':10}
agent.write_bytes(plistlib.dumps(job))
run('killall','-u',str(uid),'WallpaperAgent',check=False)
run('launchctl','bootout',f'gui/{uid}',str(agent),check=False)
run('launchctl','bootstrap',f'gui/{uid}',str(agent))
state = run('launchctl','print',f'gui/{uid}/{label}').stdout.decode()
match = re.search(r'\bpid = (\d+)',state)
print(json.dumps({'pid':int(match.group(1)) if match else None,
                  'command':str(support/'KlanglaborLockDisplay'),
                  'cwd':str(base.parents[2]),'log':str(logs),'idle_entries':count,
                  'backup':str(backup)},ensure_ascii=False))
