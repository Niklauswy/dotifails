#!/usr/bin/env python3
"""Build the Wysun shell runtime: Qt (aqtinstall), Quickshell, libcava, M3Shapes and the shell plugin.

The runtime lives in one self-contained prefix (default $XDG_DATA_HOME/wysun/runtime) and never touches
system Qt or the packaged Quickshell. Everything is pinned in manifests/runtime.json. Re-running only
rebuilds what changed: the plugin is stamped with a hash of apps/shell/{plugin,extras,CMakeLists.txt}.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import urllib.request
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STEPS = ('qt', 'deps', 'quickshell', 'plugin')


def default_prefix():
    return Path(os.environ.get('WYSUN_RUNTIME') or Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'wysun/runtime')


def run(cmd, **kw):
    print('+', ' '.join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def fetch(url, commit, dest):
    if not (dest / '.git').is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        run(['git', 'init', '-q', dest])
        run(['git', '-C', dest, 'remote', 'add', 'origin', url])
    have = subprocess.run(['git', '-C', dest, 'cat-file', '-e', commit + '^{commit}'], stderr=subprocess.DEVNULL).returncode == 0
    if not have:
        run(['git', '-C', dest, 'fetch', '--quiet', '--depth', '1', 'origin', commit])
    run(['git', '-C', dest, 'checkout', '--quiet', '--force', commit])


def shell_hash():
    digest = hashlib.sha256()
    shell = ROOT / 'apps/shell'
    # The plugin also bundles the lock's mascot shader (Wysun.Components).
    for path in sorted([shell / 'CMakeLists.txt', shell / 'modules/lockscreen/shaders/mascot.frag',
                        *shell.joinpath('plugin').rglob('*'), *shell.joinpath('extras').rglob('*')]):
        if path.is_file():
            digest.update(path.relative_to(shell).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


class Build:
    def __init__(self, prefix, jobs, cache):
        self.prefix = Path(prefix)
        self.jobs = str(jobs)
        self.cache = Path(cache)
        self.src = self.cache / 'src'
        self.manifest = json.loads((ROOT / 'manifests/runtime.json').read_text())
        self.qt_version = self.manifest['qt']['version']
        self.qt = self.prefix / 'qt' / self.qt_version / 'gcc_64'
        self.deps = self.prefix / 'deps'
        self.stamp_path = self.prefix / 'RUNTIME.json'
        self.stamp = json.loads(self.stamp_path.read_text()) if self.stamp_path.exists() else {}

    def save(self, key, value):
        self.stamp[key] = value
        self.prefix.mkdir(parents=True, exist_ok=True)
        tmp = self.stamp_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.stamp, indent=2, sort_keys=True) + '\n')
        tmp.replace(self.stamp_path)

    def env(self):
        env = dict(os.environ)
        env['PKG_CONFIG_PATH'] = os.pathsep.join(filter(None, [str(self.deps / 'lib/pkgconfig'), env.get('PKG_CONFIG_PATH', '')]))
        # WYSUN_EXTRA_PREFIX: optional extra prefixes (headers/libs) for hosts where -dev packages cannot be installed.
        for extra in filter(None, os.environ.get('WYSUN_EXTRA_PREFIX', '').split(os.pathsep)):
            env['CPATH'] = os.pathsep.join(filter(None, [str(Path(extra) / 'include'), env.get('CPATH', '')]))
            env['LIBRARY_PATH'] = os.pathsep.join(filter(None, [str(Path(extra) / 'lib'), env.get('LIBRARY_PATH', '')]))
        return env

    def cmake(self, source, build, prefix, *options):
        rpath = '%s;%s' % (self.qt / 'lib', self.deps / 'lib')
        run(['cmake', '-S', source, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             '-DCMAKE_PREFIX_PATH=' + ';'.join([str(self.qt), *filter(None, os.environ.get('WYSUN_EXTRA_PREFIX', '').split(os.pathsep))]), '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
             '-DCMAKE_INSTALL_RPATH=' + rpath, '-DCMAKE_BUILD_WITH_INSTALL_RPATH=OFF', *options], env=self.env())
        run(['cmake', '--build', build, '--parallel', self.jobs], env=self.env())
        run(['cmake', '--install', build], env=self.env())

    def qt_step(self):
        spec = self.manifest['qt']
        if (self.qt / 'bin/qmake').exists() and self.stamp.get('qt') == spec:
            return
        venv = self.cache / 'aqt-venv'
        if not (venv / 'bin/aqt').exists():
            run([sys.executable, '-m', 'venv', venv])
            run([venv / 'bin/pip', 'install', '--quiet', 'aqtinstall==' + spec['aqtinstall']])
        # aqt writes aqtinstall.log into its working directory: keep that out of the source tree.
        run([venv / 'bin/aqt', 'install-qt', 'linux', 'desktop', spec['version'], spec['arch'],
             '-O', self.prefix / 'qt', '-m', *spec['modules']], cwd=self.cache)
        self.save('qt', spec)

    def deps_step(self):
        sources = self.manifest['sources']
        if self.stamp.get('deps') == [sources['libcava'], sources['m3shapes']] and (self.deps / 'lib/libcava.so').exists():
            return
        src = self.src / 'cava'
        fetch(sources['libcava']['url'], sources['libcava']['commit'], src)
        build = self.cache / 'build/cava'
        # cava's own CMake only knows the executable; we need the shared core with a pkg-config file.
        core = self.cache / 'build/cava-core'
        core.mkdir(parents=True, exist_ok=True)
        (core / 'CMakeLists.txt').write_text(CAVA_CORE_CMAKE.replace('@SRC@', str(src)).replace('@VERSION@', sources['libcava']['version']))
        self.cmake(core, build, self.deps)
        fetch(sources['m3shapes']['url'], sources['m3shapes']['commit'], self.src / 'm3shapes')
        self.cmake(self.src / 'm3shapes', self.cache / 'build/m3shapes', self.deps)
        self.save('deps', [sources['libcava'], sources['m3shapes']])

    def protocols(self):
        """Quickshell needs newer Wayland protocol XML than Debian 13 ships; keep it in the runtime prefix."""
        spec = self.manifest['sources']['wayland_protocols']
        pc = self.deps / 'lib/pkgconfig/wayland-protocols.pc'
        if pc.exists() and self.stamp.get('wayland_protocols') == spec:
            return
        archive = self.cache / 'wayland-protocols.tar.gz'
        archive.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(spec['url'], archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['sha256']:
            raise RuntimeError('wayland-protocols: suma de verificación distinta de la fijada')
        data = self.deps / 'share/wayland-protocols'
        shutil.rmtree(data, ignore_errors=True)
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if m.name.split('/')[1:2] and m.name.split('/')[1] in ('stable', 'staging', 'unstable')]
            tar.extractall(self.cache / 'wp-extract', members=members, filter='data')
        for kind in ('stable', 'staging', 'unstable'):
            shutil.copytree(self.cache / 'wp-extract' / ('wayland-protocols-' + spec['version']) / kind, data / kind)
        pc.parent.mkdir(parents=True, exist_ok=True)
        pc.write_text('prefix=%s\npkgdatadir=${prefix}/share/wayland-protocols\nName: Wayland Protocols\n'
                      'Description: Wayland protocol definitions pinned for the Wysun runtime\nVersion: %s\n'
                      % (self.deps, spec['version']))
        self.save('wayland_protocols', spec)

    def quickshell_step(self):
        spec = self.manifest['sources']['quickshell']
        self.protocols()
        if self.stamp.get('quickshell') == spec and (self.prefix / 'quickshell/bin/quickshell').exists():
            return
        src = self.src / 'quickshell'
        fetch(spec['url'], spec['commit'], src)
        self.cmake(src, self.cache / 'build/quickshell', self.prefix / 'quickshell',
                   '-DDISTRIBUTOR=Wysun', '-DCRASH_HANDLER=OFF', '-DUSE_JEMALLOC=OFF', '-DGIT_REVISION=' + spec['commit'])
        self.save('quickshell', spec)

    def plugin_step(self):
        digest = shell_hash()
        target = self.prefix / 'shell'
        if self.stamp.get('plugin') == digest and (target / 'lib/wysun/version').exists():
            return
        revision = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL).stdout.strip() or '0' * 40
        self.cmake(ROOT / 'apps/shell', self.cache / 'build/shell', target,
                   '-DENABLE_MODULES=extras;plugin', '-DVERSION=1.0.0', '-DGIT_REVISION=' + revision,
                   '-DDISTRIBUTOR=Wysun', '-DINSTALL_LIBDIR=lib/wysun', '-DINSTALL_QMLDIR=lib/qt6/qml')
        self.save('plugin', digest)


CAVA_CORE_CMAKE = '''cmake_minimum_required(VERSION 3.16)
project(libcava VERSION @VERSION@ LANGUAGES C)
find_path(FFTW3_INCLUDE fftw3.h REQUIRED)
find_library(FFTW3_LIB fftw3 REQUIRED)
add_library(cava SHARED @SRC@/src/cavacore.c)
target_include_directories(cava PUBLIC @SRC@/include PRIVATE ${FFTW3_INCLUDE})
target_link_libraries(cava PRIVATE ${FFTW3_LIB} m)
set_target_properties(cava PROPERTIES POSITION_INDEPENDENT_CODE ON)
include(GNUInstallDirs)
install(TARGETS cava LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES @SRC@/include/cava/cavacore.h DESTINATION include/cava)
file(WRITE ${CMAKE_BINARY_DIR}/libcava.pc
"prefix=${CMAKE_INSTALL_PREFIX}\\nlibdir=${CMAKE_INSTALL_PREFIX}/lib\\nincludedir=${CMAKE_INSTALL_PREFIX}/include\\n"
"Name: libcava\\nDescription: cava audio analysis core\\nVersion: @VERSION@\\nLibs: -L${CMAKE_INSTALL_PREFIX}/lib -lcava\\nCflags: -I${CMAKE_INSTALL_PREFIX}/include\\n")
install(FILES ${CMAKE_BINARY_DIR}/libcava.pc DESTINATION lib/pkgconfig)
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--prefix', default=str(default_prefix()))
    parser.add_argument('--cache', default=str(Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'wysun/build'))
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    parser.add_argument('--only', default=','.join(STEPS), help='comma list of: ' + ', '.join(STEPS))
    parser.add_argument('--print-packages', action='store_true', help='print the APT build dependencies and exit')
    args = parser.parse_args(argv)
    manifest = json.loads((ROOT / 'manifests/runtime.json').read_text())
    if args.print_packages:
        print(' '.join(manifest['build_packages']))
        return 0
    wanted = [s for s in STEPS if s in args.only.split(',')]
    build = Build(args.prefix, args.jobs, args.cache)
    for step in wanted:
        print('==> ' + step, flush=True)
        getattr(build, step + '_step')()
    print('RUNTIME_OK ' + str(build.prefix))
    return 0


if __name__ == '__main__':
    sys.exit(main())
