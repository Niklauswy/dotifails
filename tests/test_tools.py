"""Regression tests isolate HTTP, project data, providers and firewall state."""
import argparse
import base64
import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/tools'))
from orbit_tools import common, web, security, transfer, cloud, vpn
from orbit_tools import resets as rezets
spec=importlib.util.spec_from_file_location('toolbox_installer',ROOT/'installer/main.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class ToolboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_lockfile_conflicts_and_declared_manager(self):
        (self.root/'package.json').write_text('{"packageManager":"pnpm@10"}')
        (self.root/'pnpm-lock.yaml').touch()
        self.assertEqual(web.project(self.root)[2],'pnpm')
        (self.root/'package-lock.json').touch()
        with self.assertRaises(common.ToolError):web.project(self.root)
    def test_framework_arguments_and_no_missing_script_execution(self):
        p={'scripts':{'dev':'next dev'},'dependencies':{'next':'1'}}
        self.assertEqual(web.script_command(p,'npm','dev',[],3000,'127.0.0.1'),['npm','run','dev','--','--port','3000','--hostname','127.0.0.1'])
        with self.assertRaises(common.ToolError):web.script_command(p,'npm','build',[])
    def test_web_dry_run_does_not_open_socket_or_execute(self):
        (self.root/'package.json').write_text('{"scripts":{"dev":"vite"},"devDependencies":{"vite":"1"}}')
        with patch.object(web.socket,'socket',side_effect=AssertionError('socket opened')),patch.object(web.os,'execvp',side_effect=AssertionError('executed')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(web.main(['dev','-C',str(self.root),'--port','3000','--dry-run']),0)
    def test_env_never_prints_values(self):
        (self.root/'.env.example').write_text('API_KEY=example\nMISSING=1\n')
        (self.root/'.env').write_text('API_KEY=very-private-value\nAPI_KEY=another-private-value\n')
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=web.main(['env','-C',str(self.root),'--json'])
        self.assertEqual(code,1); self.assertNotIn('private-value',output.getvalue());self.assertIn('MISSING',output.getvalue())
    def test_private_atomic_reports_refuse_overwrite(self):
        p=self.root/'report.json';common.private_write(p,'old',overwrite=False)
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):common.private_write(p,'new',overwrite=False)
        self.assertEqual(p.read_text(),'old')
        common.private_write(p,'updated');self.assertEqual(p.read_text(),'updated')
    def test_nested_report_redaction(self):
        result=common.report('test');result['data']['remote']=['password=private-value']
        output=io.StringIO()
        with contextlib.redirect_stdout(output):common.emit(result,argparse.Namespace(json=True))
        self.assertNotIn('private-value',output.getvalue())
    def test_scan_scopes_and_ipv6(self):
        a=argparse.Namespace(target='10.0.0.0/24',max_hosts=64,rate=100,timeout=5,ports='22,80-90',services=False)
        with self.assertRaises(common.ToolError):security.nmap_command(a)
        a.target='::1';self.assertIn('-6',security.nmap_command(a));self.assertIn('-sT',security.nmap_command(a));self.assertNotIn('-sC',security.nmap_command(a))
        for ports in ('0','22-1','65536','22;whoami'):
            with self.assertRaises(common.ToolError):security.port_spec(ports)
    def test_nmap_structured_results(self):
        rows=security.parse_nmap('<nmaprun><host><address addr="127.0.0.1" addrtype="ipv4"/><ports><port portid="80" protocol="tcp"><state state="open"/><service name="http"/></port></ports></host></nmaprun>')
        self.assertEqual(rows[0]['ports'][0]['port'],80)
        with self.assertRaises(common.ToolError):security.parse_nmap('not xml')
    def test_git_scan_redacts_and_skips_symlinks(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        value='ghp_'+'A'*36
        (self.root/'source.txt').write_text('key='+value)
        (self.root/'linked').symlink_to(self.root/'source.txt')
        subprocess.run(['git','-C',str(self.root),'add','source.txt','linked'],check=True)
        findings,count=security.project_findings(self.root)
        self.assertEqual(count,1);self.assertEqual(findings[0]['rule'],'token GitHub')
        self.assertNotIn(value,json.dumps(findings))
    def test_single_cli_routes_and_aliases_share_one_backend(self):
        spec=importlib.util.spec_from_file_location('tools_cli',ROOT/'apps/tools/cli.py');cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        with patch.object(web,'main',return_value=0) as main:
            self.assertEqual(cli.main(['dev','doctor']),0);main.assert_called_with(['doctor'])
            self.assertEqual(cli.main(['web-dev','doctor']),0);main.assert_called_with(['doctor'])
    def test_retire_preserves_local_edits_and_restore_recovers_removed_file(self):
        home=self.root/'home';home.mkdir();source=home/'legacy';source.write_text('old')
        d=installer.Deployment(home,ROOT);d.begin();d.receipt['files']['legacy']=installer.fingerprint(source)
        d.retire(Path('legacy'));d.finish();d.lock.close();self.assertFalse(source.exists())
        with contextlib.redirect_stdout(io.StringIO()):installer.restore(home,d.journal['id'])
        self.assertEqual(source.read_text(),'old')
        d=installer.Deployment(home,ROOT);d.begin();d.receipt['files']['legacy']=installer.fingerprint(source);source.write_text('user changed')
        d.retire(Path('legacy'));d.lock.close();self.assertEqual(source.read_text(),'user changed');self.assertIn('legacy',d.conflicts)
    def test_cloud_explicit_argv_and_remote_validation(self):
        args=argparse.Namespace(action='stop',account='example@example.test')
        cmd,body=cloud.command(args,['project','zone','instance'])
        self.assertIn('--project',cmd);self.assertIn('--account',cmd);self.assertIsNone(body)
        with self.assertRaises(argparse.ArgumentTypeError):cloud.target('project/zone/instance;bad')
        with self.assertRaises(argparse.ArgumentTypeError):cloud.remote_path('/tmp/file;bad')
    def test_cloud_reports_partial_failures(self):
        def fake(argv,**kwargs):
            if '--project' in argv and argv[argv.index('--project')+1]=='bad':
                return subprocess.CompletedProcess(argv,1,'','permission denied')
            return subprocess.CompletedProcess(argv,0,'[{"name":"vm","zone":"zones/zone","status":"RUNNING"}]','')
        with patch.object(cloud,'run',side_effect=fake):
            result=cloud.instances(argparse.Namespace(project=['ok','bad'],all_projects=False,account=None,jobs=2))
        self.assertEqual(len(result['data']['instances']),1)
        self.assertTrue(any(c['status']=='fail' for c in result['checks']))
    def test_cloud_mutation_failure_is_not_success(self):
        output=io.StringIO()
        with patch.object(cloud,'require',return_value='gcloud'),patch.object(cloud,'run',return_value=subprocess.CompletedProcess([],7,'','failed')),contextlib.redirect_stdout(output):
            code=cloud.main(['stop','--vm','project/zone/vm','--json'])
        self.assertEqual(code,1);self.assertIn('Código 7',output.getvalue())
    def test_cloud_dry_run_never_calls_provider(self):
        with patch.object(cloud,'run',side_effect=AssertionError('provider called')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cloud.main(['delete','--vm','project/zone/vm','--dry-run']),0)
    def test_firewall_owned_rules_not_global_policies(self):
        text=vpn.rules();self.assertIn('table inet orbit_tailscale_lock',text)
        self.assertIn('0xff0000 == 0x80000',text);self.assertIn('policy drop',text)
        self.assertNotIn('flush ruleset',text);self.assertNotIn('ct state established',text)
        with self.assertRaises(common.ToolError):vpn.rules('bad";accept')
    def test_vpn_dry_run_has_no_privileged_calls(self):
        with patch.object(vpn,'run',side_effect=AssertionError('firewall called')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(vpn.main(['on','100.64.0.1','--dry-run']),0)
    def test_vpn_off_preserves_firewall_if_restore_fails(self):
        p=self.root/'state';common.private_write(p,json.dumps({'previous':{'exit_node':'','allow_lan':False,'dns':True}}))
        with patch.object(vpn,'STATE',p),patch.object(vpn.os,'geteuid',return_value=0),patch.object(vpn,'owned_table',return_value=True),patch.object(vpn,'restore_prefs',side_effect=common.ToolError('failed')),patch.object(vpn,'run') as run:
            with self.assertRaises(common.ToolError):vpn.off(argparse.Namespace(dry_run=False))
            run.assert_not_called();self.assertTrue(p.exists())
    def test_vpn_off_restores_then_deletes_owned_table(self):
        p=self.root/'state';common.private_write(p,json.dumps({'previous':{}}));events=[]
        with patch.object(vpn,'STATE',p),patch.object(vpn.os,'geteuid',return_value=0),patch.object(vpn,'owned_table',return_value=True),patch.object(vpn,'require',return_value='nft'),patch.object(vpn,'restore_prefs',side_effect=lambda _:events.append('restore')),patch.object(vpn,'run',side_effect=lambda argv:events.append(argv)),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(vpn.off(argparse.Namespace(dry_run=False)),0)
        self.assertEqual(events[0],'restore');self.assertEqual(events[1],['nft','delete','table','inet',vpn.TABLE]);self.assertFalse(p.exists())
    def test_vpn_on_failure_rolls_back_preferences_then_firewall(self):
        state=self.root/'state';events=[]
        prefs={'ExitNodeIP':'','ExitNodeAllowLANAccess':True,'CorpDNS':False}
        def fake_run(argv,**kwargs):
            events.append(argv)
            if argv[:2]==['tailscale','set'] and '--exit-node=100.64.0.2' in argv:
                self.assertTrue(state.exists())
                self.assertEqual(json.loads(state.read_text())['phase'],'armed')
                raise common.ToolError('provider failure')
            return subprocess.CompletedProcess(argv,0,'','')
        args=argparse.Namespace(exit_node='100.64.0.2',interface='lo',dry_run=False)
        with patch.object(vpn,'STATE',state),patch.object(vpn.os,'geteuid',return_value=0),patch.object(vpn,'owned_table',return_value=False),patch.object(vpn,'require',side_effect=lambda x:x),patch.object(vpn,'provider_json',side_effect=[prefs,{}]),patch.object(vpn,'run',side_effect=fake_run):
            with self.assertRaises(common.ToolError):vpn.on(args)
        self.assertIn('--exit-node=',events[-2]);self.assertEqual(events[-1],['nft','delete','table','inet',vpn.TABLE]);self.assertFalse(state.exists())
    def test_vpn_failed_recovery_keeps_armed_state(self):
        state=self.root/'state';events=[]
        def fake_run(argv,**kwargs):
            events.append(argv)
            if argv[:2]==['tailscale','set']:raise common.ToolError('provider unavailable')
            return subprocess.CompletedProcess(argv,0,'','')
        args=argparse.Namespace(exit_node='100.64.0.2',interface='lo',dry_run=False)
        with patch.object(vpn,'STATE',state),patch.object(vpn.os,'geteuid',return_value=0),patch.object(vpn,'owned_table',return_value=False),patch.object(vpn,'require',side_effect=lambda x:x),patch.object(vpn,'provider_json',side_effect=[{},{}]),patch.object(vpn,'run',side_effect=fake_run):
            with self.assertRaisesRegex(common.ToolError,'Recuperación pendiente'):vpn.on(args)
        self.assertEqual(json.loads(state.read_text())['phase'],'armed')
        self.assertFalse(any(argv[:3]==['nft','delete','table'] for argv in events))
    def test_rezets_atomic_save_and_invalid_minutes(self):
        p=self.root/'accounts.json'
        with patch.object(rezets,'CONFIG_FILE',p),patch.object(rezets,'APP_DIR',self.root):
            rezets.save_accounts([rezets.Account('lab','test',[rezets.ResetPoint('weekly','2027-01-01T10:00:00-08:00')])])
            self.assertEqual(rezets.load_accounts()[0].name,'lab');self.assertEqual(p.stat().st_mode&0o777,0o600)
            rezets.save_accounts([]);self.assertTrue(p.with_suffix('.json.bak').exists())
        with self.assertRaises(ValueError):rezets.parse_time_of_day('10:99',rezets.datetime.now().astimezone())
    def test_rezets_migration_preserves_original(self):
        home=self.root/'home';legacy=home/'scripts/.rezets/accounts.json';legacy.parent.mkdir(parents=True)
        text='[{"name":"lab","service":"test","reset_at":"2027-01-01T10:00:00Z"}]';legacy.write_text(text)
        p=self.root/'new/accounts.json'
        with patch.object(rezets.Path,'home',return_value=home),patch.object(rezets,'CONFIG_FILE',p),patch.object(rezets,'APP_DIR',p.parent):
            self.assertEqual(rezets.load_accounts()[0].name,'lab')
        self.assertEqual(legacy.read_text(),text);self.assertEqual(p.read_text(),text)
    def test_scripts_install_preserves_private_files_and_idempotence(self):
        home=self.root/'home';private=home/'scripts/.rezets/accounts.json';private.parent.mkdir(parents=True);private.write_text('[]')
        upload=home/'scripts/uploads/data';upload.parent.mkdir();upload.write_text('upload')
        config=home/'.config/orbit/theme.json';config.parent.mkdir(parents=True);config.write_text('theme')
        old=home/'scripts/gvm.sh';old.write_text('old script')
        receipt=home/'.local/state/dotifails/installed.json';receipt.parent.mkdir(parents=True);receipt.write_text(json.dumps({'files':{'scripts/gvm.sh':installer.fingerprint(old)}}))
        args=['install','--source',str(ROOT),'--target-home',str(home),'--scripts-only']
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(args),0)
            first=json.loads((home/'.local/state/dotifails/installed.json').read_text())['last_backup']
            self.assertEqual(installer.main(args),0)
        self.assertEqual((home/'.config/orbit/resets/accounts.json').read_text(),'[]');self.assertEqual((home/'.local/share/orbit/transfers/inbox/data').read_text(),'upload');self.assertEqual(config.read_text(),'theme')
        receipt=json.loads((home/'.local/state/dotifails/installed.json').read_text());journal=json.loads((home/'.local/state/dotifails/backups'/receipt['last_backup']/'journal.json').read_text())
        self.assertEqual(journal['operations'],[])
        self.assertTrue((home/'.local/bin/orbit-tools').is_file());self.assertFalse((home/'scripts/gvm.sh').exists())
        with contextlib.redirect_stdout(io.StringIO()):installer.restore(home,first)
        self.assertEqual(old.read_text(),'old script');self.assertEqual(private.read_text(),'[]')

class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.share=self.root/'share';self.share.mkdir()
        (self.share/'visible.txt').write_text('visible');(self.share/'.env').write_text('private')
        outside=self.root/'outside';outside.write_text('outside');(self.share/'escape').symlink_to(outside)
        self.uploads=self.root/'uploads';self.uploads.mkdir()
        self.server=transfer.TransferServer(('127.0.0.1',0),self.share,uploads=self.uploads,max_bytes=16,code='test-access-code',quiet=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.auth='Basic '+base64.b64encode(b'orbit:test-access-code').decode()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,method,path,body=None,auth=True,**headers):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        if auth:headers['Authorization']=self.auth
        conn.request(method,path,body=body,headers=headers);response=conn.getresponse();data=response.read();status=response.status;h=dict(response.getheaders());conn.close();return status,data,h
    def test_auth_and_download(self):
        self.assertEqual(self.request('GET','/visible.txt',auth=False)[0],401)
        code,data,headers=self.request('GET','/visible.txt');self.assertEqual((code,data),(200,b'visible'));self.assertIn('attachment',headers['Content-Disposition'])
    def test_hidden_traversal_symlink_and_listing(self):
        for path in ('/.env','/escape','/%2e%2e/outside'):
            self.assertEqual(self.request('GET',path)[0],403,path)
        code,data,_=self.request('GET','/');self.assertEqual(code,200);self.assertNotIn(b'.env',data);self.assertNotIn(b'escape',data)
    def test_upload_limits_and_no_overwrite(self):
        for body in (b'first',b'second'):
            code,data,_=self.request('PUT','/api/upload',body,**{'X-Filename':'file.txt'})
            self.assertEqual(code,201)
            last_name=json.loads(data)['name']
        self.assertEqual((self.uploads/'file.txt').read_bytes(),b'first');self.assertEqual((self.uploads/last_name).read_bytes(),b'second')
        self.assertEqual(self.request('PUT','/api/upload',b'x'*17,**{'X-Filename':'large.txt'})[0],413)
        self.assertFalse((self.uploads/'large.txt').exists())
        self.assertEqual(self.request('PUT','/api/upload',b'a',**{'X-Filename':'.env'})[0],400)
    def test_upload_basename_and_private_mode(self):
        code,_,_=self.request('PUT','/api/upload',b'ok',**{'X-Filename':'..%2Foutside.txt'})
        self.assertEqual(code,201);self.assertEqual((self.uploads/'outside.txt').stat().st_mode&0o777,0o600)
    def test_partial_upload_is_not_published(self):
        import socket
        conn=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3)
        request=f'PUT /api/upload HTTP/1.0\r\nAuthorization: {self.auth}\r\nContent-Length: 10\r\nX-Filename: partial.txt\r\n\r\n'.encode()
        conn.sendall(request+b'abc');conn.shutdown(socket.SHUT_WR)
        self.assertIn(b'400',conn.recv(4096));conn.close()
        self.assertFalse((self.uploads/'partial.txt').exists())
    def test_http_auditor_against_real_fixture(self):
        # Authenticate header is deliberately absent; expect validates the 401 status.
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=security.main(['http',f'http://127.0.0.1:{self.server.server_port}/visible.txt','--expect','401','--json'])
        result=json.loads(output.getvalue())
        self.assertTrue(any(c['name']=='Estado HTTP' and c['status']=='pass' for c in result['checks']))
        self.assertNotIn('test-access-code',output.getvalue())
    @unittest.skipUnless(common.executable('nmap'),'Nmap opcional no instalado')
    def test_real_tcp_scan_detects_fixture_port(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=security.main(['ports','127.0.0.1','--ports',str(self.server.server_port),'--timeout','5','--json'])
        result=json.loads(output.getvalue())
        self.assertEqual(code,0)
        ports=[p['port'] for host in result['data']['hosts'] for p in host['ports'] if p['state']=='open']
        self.assertIn(self.server.server_port,ports)
    def test_transfer_page_escapes_names_and_limits_and_has_no_external_assets(self):
        (self.share/'<img src=x onerror=alert(1)>.txt').write_text('fixture')
        code,data,headers=self.request('GET','/')
        self.assertEqual(code,200);self.assertIn(b'&lt;img',data);self.assertNotIn(b'<img src=x',data)
        self.assertIn(b'data-max-bytes="16"',data);self.assertIn(b'id="dropzone"',data)
        self.assertIn(b'prefers-reduced-motion',data);self.assertNotIn(b'<script src=',data)
        self.assertIn("base-uri 'none'",headers['Content-Security-Policy'])
    def test_hidden_symlink_target_is_not_listed(self):
        (self.share/'public-looking').symlink_to(self.share/'.env')
        self.assertNotIn(b'public-looking',self.request('GET','/')[1])
    def test_head_protection_and_csp(self):
        self.assertEqual(self.request('HEAD','/.env')[0],403)
        self.assertIn('Content-Security-Policy',self.request('GET','/')[2])


@unittest.skipUnless(common.executable('openssl'),'OpenSSL opcional no instalado')
class TLSTests(unittest.TestCase):
    def setUp(self):
        import ssl
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cert=self.root/'cert.pem';key=self.root/'key.pem'
        subprocess.run([common.require('openssl'),'req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost','-keyout',str(key),'-out',str(self.cert)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(self.cert,key)
        self.server=transfer.TransferServer(('127.0.0.1',0),self.root,quiet=True)
        self.server.enable_tls(context)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def test_tls_trusted_certificate_and_expiry(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=security.main(['tls','127.0.0.1','--port',str(self.server.server_port),'--server-name','localhost','--ca-file',str(self.cert),'--days','1','--json'])
        result=json.loads(output.getvalue());self.assertEqual(code,0);self.assertIn('expires_at',result['data'])
        self.assertTrue(any(c['name']=='Certificado y nombre' and c['status']=='pass' for c in result['checks']))
    def test_idle_tls_connection_does_not_block_other_clients(self):
        import socket
        idle=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code=security.main(['tls','127.0.0.1','--port',str(self.server.server_port),'--server-name','localhost','--ca-file',str(self.cert),'--timeout','2','--json'])
            self.assertEqual(code,0)
        finally:idle.close()
    def test_tls_untrusted_certificate_fails(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code=security.main(['tls','127.0.0.1','--port',str(self.server.server_port),'--json'])
        self.assertEqual(code,1)

if __name__=='__main__':unittest.main()
