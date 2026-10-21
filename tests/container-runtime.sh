#!/bin/sh
# Disposable Debian 13 container only; see docs/validation.md.
set -eu
[ "${WYSUN_CONTAINER_TEST:-}" = 1 ] || { echo 'Requires WYSUN_CONTAINER_TEST=1' >&2; exit 2; }
[ -f /run/.containerenv ] || [ -f /.dockerenv ] || { echo 'Requires disposable container' >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo 'Container root required for build dependencies' >&2; exit 2; }
. /etc/os-release
[ "$ID" = debian ] && [ "$VERSION_ID" = 13 ] || { echo 'Requires Debian 13' >&2; exit 2; }
export DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
printf '#!/bin/sh\nexit 101\n' >/usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
if [ -f /root/rt/RUNTIME.json ]; then
    # Reuse only a complete matching artifact. Never restart compilation on a
    # validation retry; install just missing manifest packages in this container.
    python3 - <<'CHECK'
import importlib.util,pathlib
spec=importlib.util.spec_from_file_location('runtime_build','/src/installer/runtime_build.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=m.Build('/root/rt',2,'/root/.cache/wysun/build');sources=b.manifest['sources']
assert b.stamp == {'qt':b.manifest['qt'],'deps':[sources['libcava'],sources['m3shapes']],
    'wayland_protocols':sources['wayland_protocols'],'quickshell':sources['quickshell'],'plugin':m.shell_hash()}, 'Existing runtime differs; no rebuild was started'
print('WYSUN_RUNTIME_REUSE_MATCHED')
CHECK
    packages=$(python3 /src/installer/runtime_build.py --print-packages)
    missing=""
    for package in $packages; do
        if [ "$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)" != installed ]; then
            missing="$missing $package"
        fi
    done
    if [ -n "$missing" ]; then
        apt-get install -y --no-install-recommends --no-upgrade $missing
    fi
else
    apt-get update
    apt-get install -y --no-install-recommends python3 ca-certificates
    packages=$(python3 /src/installer/runtime_build.py --print-packages)
    apt-get install -y --no-install-recommends $packages
    python3 /src/installer/runtime_build.py --prefix /root/rt --cache /root/.cache/wysun/build --jobs "${WYSUN_BUILD_JOBS:-2}"
fi
/root/rt/quickshell/bin/quickshell --version
python3 - <<'PY'
import hashlib,json,pathlib,subprocess
root=pathlib.Path('/root/rt')
stamp=root/'RUNTIME.json'
state=json.loads(stamp.read_text())
assert set(state)=={'qt','deps','wayland_protocols','quickshell','plugin'},state
plugins=list((root/'shell/lib/qt6/qml/Wysun').rglob('*.so'))
assert plugins,'No Wysun plugins installed'
for binary in [root/'quickshell/bin/quickshell',*plugins]:
    result=subprocess.run(['ldd',str(binary)],capture_output=True,text=True,check=True)
    assert 'not found' not in result.stdout,(str(binary),result.stdout)
# An unchanged build must retain all stamp values and skip all build commands.
before=hashlib.sha256(stamp.read_bytes()).hexdigest()
result=subprocess.run(['python3','/src/installer/runtime_build.py','--prefix',str(root),
                       '--cache','/root/.cache/wysun/build','--jobs','2'],capture_output=True,text=True,check=True)
assert '\n+ ' not in '\n'+result.stdout,result.stdout
assert hashlib.sha256(stamp.read_bytes()).hexdigest()==before
print('Runtime manifest SHA256:',hashlib.sha256(pathlib.Path('/src/manifests/runtime.json').read_bytes()).hexdigest())
print('Runtime stamps:',json.dumps(state,sort_keys=True))
print('WYSUN_RUNTIME_CONTAINER_OK: Debian 13 artifact, Qt/dependencies/Quickshell/Wysun plugins, ldd and unchanged rebuild; no physical session')
PY
