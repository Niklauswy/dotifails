#!/bin/sh
# Run only inside the disposable, resource-limited container described in docs.
set -eu
[ "${WYSUN_CONTAINER_TEST:-}" = 1 ] || { echo 'Requires WYSUN_CONTAINER_TEST=1 in a disposable container' >&2; exit 2; }
[ -f /run/.containerenv ] || [ -f /.dockerenv ] || { echo 'No container marker' >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo 'Container bootstrap requires container root' >&2; exit 2; }
export DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
printf '#!/bin/sh\nexit 101\n' >/usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get update
apt-get install --no-install-recommends --yes python3 sudo ca-certificates
printf 'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie-backports main\n' >/etc/apt/sources.list.d/wysun-backports.list
apt-get update
test_user=${WYSUN_CONTAINER_USER:-wysuntest}
case "$test_user" in wysuntest|wysunfinal) ;; *) echo 'Invalid isolated test user' >&2; exit 2 ;; esac
test_source=${WYSUN_CONTAINER_SOURCE:-/test-source}
case "$test_source" in /test-source|/test-source-final) ;; *) echo 'Invalid isolated source' >&2; exit 2 ;; esac
useradd --create-home --shell /bin/sh "$test_user"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$test_user" >"/etc/sudoers.d/$test_user"
chmod 440 "/etc/sudoers.d/$test_user"
# A rootless bind mount preserves host ownership, including legitimate mode0600
# source files. Model a real checkout owned by the installing user instead.
mkdir "$test_source"
cp -a /src/. "$test_source/"
chown -R "$test_user:$test_user" "$test_source"
runuser -u "$test_user" -- env HOME="/home/$test_user" PATH="/home/$test_user/.local/bin:/usr/local/bin:/usr/bin:/bin" QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR="/home/$test_user/run" WYSUN_CONTAINER_SOURCE="$test_source" /usr/bin/python3 - <<'PY'
import hashlib,json,os,subprocess,shutil
from pathlib import Path
source_path=Path(os.environ['WYSUN_CONTAINER_SOURCE'])
home=Path.home();(home/'run').mkdir(mode=0o700)
fixtures={'.config/bspwm/bspwmrc':'custom BSPWM fixture\n',
          '.config/bspwm/picom.conf':'custom Picom fixture\n',
          '.config/sxhkd/sxhkdrc':'custom SXHKD fixture\n',
          '.config/orbit/personal.json':'{"fixture":true}\n',
          '.local/share/orbit/notes/private.md':'synthetic note fixture\n',
          '.local/share/loomrec/recordings/fixture/project.json':'synthetic project\n',
          '.local/share/wybie-screenshot/sessions/fixture/original.png':'synthetic image bytes\n'}
for relative,text in fixtures.items():
    p=home/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
def check():
    for relative,text in fixtures.items():assert (home/relative).read_text()==text,relative
def run(*argv):subprocess.run(argv,check=True,cwd='/')
run('/usr/bin/python3',str(source_path/'installer/main.py'),'install','--source',str(source_path),'--components','wayland')
check()
assert Path('/usr/share/wayland-sessions/wysun-hyprland.desktop').is_file()
run('wysun','session-check')
run('wysun','recorder','--version');run('wysun','screenshot','--version')
run('/usr/bin/python3',str(source_path/'installer/main.py'),'install','--source',str(source_path),'--components','wayland','--config-only')
check()
receipt=json.loads((home/'.local/state/dotifails/installed.json').read_text())
journal=json.loads((home/'.local/state/dotifails/backups'/receipt['last_backup']/'journal.json').read_text())
assert journal['operations']==[],journal['operations']
config=home/'.config/wysun/hyprland.lua';config.write_text('-- synthetic local bindings\n')
run('/usr/bin/python3',str(source_path/'installer/main.py'),'install','--source',str(source_path),'--wysun-only')
assert config.read_text()=='-- synthetic local bindings\n';check()
# Recover a genuine application update, with both immutable versions retained.
source=home/'updated-source';source.mkdir()
for relative in ('installer','manifests','apps','bin','home','backgrounds'):
    shutil.copytree(source_path/relative,source/relative,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
entry=source/'apps/capture/loomrec/__main__.py';entry.write_text(entry.read_text()+'\n# synthetic upgrade\n')
run('/usr/bin/python3',str(source/'installer/main.py'),'install','--source',str(source),'--wysun-only')
receipt=json.loads((home/'.local/state/dotifails/installed.json').read_text());upgrade=receipt['last_backup']
releases=home/'.local/share/wysun/capture/releases';assert len(list(releases.iterdir()))==2
run('/usr/bin/python3',str(source_path/'installer/main.py'),'restore',upgrade)
assert len(list(releases.iterdir()))==2
run('wysun','recorder','--version');check()
app=home/'.local/share/orbit/app/orbit.py';app.write_text(app.read_text()+'\n# local app fixture\n')
current=app.read_bytes()
result=subprocess.run(['/usr/bin/python3',str(source_path/'installer/main.py'),'install','--source',str(source),'--wysun-only'],cwd='/')
assert result.returncode==2 and app.read_bytes()==current;check()
print('WYSUN_CLEAN_CONTAINER_OK: actual Debian packages + common installer + repeat/update/conflict/restore; no login or physical devices',flush=True)
PY
