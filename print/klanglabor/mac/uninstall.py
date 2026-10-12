#!/usr/bin/env python3
"""Restore the screen saver settings saved by install.py."""
from pathlib import Path
import os,plistlib,subprocess
library=Path('~/Library').expanduser()
support=library/'Application Support/Klanglabor Screen Saver'
backup=plistlib.loads((support/'original-settings.plist').read_bytes())
label='de.359records.klanglabor.lock-display'
subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}/{label}'],check=False)
agent=library/'LaunchAgents'/f'{label}.plist'
agent.unlink(missing_ok=True)
store=library/'Application Support/com.apple.wallpaper/Store/Index.plist'
current=plistlib.loads(store.read_bytes())
def restore_idle(node,old):
    if not isinstance(node,dict) or not isinstance(old,dict): return
    if isinstance(node.get('Idle'),dict) and 'Idle' in old:
        choices=node['Idle'].get('Content',{}).get('Choices',[])
        if choices:
            config=choices[0].get('Configuration',b'')
            try: own=plistlib.loads(config).get('module',{}).get('relative','').endswith('/Klanglabor.saver')
            except Exception: own=False
            if own: node['Idle']=old['Idle']
    for key in node:
        if key not in ['Idle','Desktop']: restore_idle(node[key],old.get(key))
restore_idle(current,backup['WallpaperStore'])
store.write_bytes(plistlib.dumps(current,fmt=plistlib.FMT_BINARY))
for host,keys in [(True,['moduleDict']),(False,['askForPassword','askForPasswordDelay'])]:
    original=backup['HostPreferences' if host else 'UserPreferences']
    prefix=['defaults']+(['-currentHost'] if host else [])
    for key in keys:
        if key not in original:
            subprocess.run(prefix+['delete','com.apple.screensaver',key],check=False)
        else:
            value=original[key]
            command=prefix+['write','com.apple.screensaver',key]
            if isinstance(value,dict):
                command+=['-dict']
                for field,entry in value.items():
                    command += [field,'-int' if isinstance(entry,int) else '-string',str(entry)]
            else:
                command += ['-int',str(int(value))]
            subprocess.run(command,check=True)
subprocess.run(['killall','-u',str(os.getuid()),'WallpaperAgent'],check=False)
print('Klanglabor-Autostart beendet und vorheriger Bildschirmschoner wiederhergestellt.')
