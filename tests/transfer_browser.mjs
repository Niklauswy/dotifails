// Browser verification through Chromium CDP, using only Node standard libraries.
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'..');
const temp=await mkdtemp(path.join(tmpdir(),'orbit-transfer-browser-'));
const artifacts='/tmp/orbit-transfer-preview';await mkdir(artifacts,{recursive:true});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let chrome,fixture,ws;const pending=new Map();let counter=0;const errors=[];
async function cdp(method,params={}) {
  const id=++counter;
  const result=new Promise((resolve,reject)=>pending.set(id,{resolve,reject}));
  ws.send(JSON.stringify({id,method,params}));return result;
}
async function evaluate(expression) {
  const result=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(result.exceptionDetails)throw new Error(result.exceptionDetails.text+' '+JSON.stringify(result.exceptionDetails.exception));
  return result.result.value;
}
async function wait(expression,limit=5000) {
  const end=Date.now()+limit;
  while(Date.now()<end){if(await evaluate(expression))return;await sleep(50);}
  throw new Error('Timeout: '+expression);
}
async function screenshot(name){const result=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile(path.join(artifacts,name+'.png'),Buffer.from(result.data,'base64'));}
async function files(paths){await cdp('DOM.enable');const {root:doc}=await cdp('DOM.getDocument');const {nodeId}=await cdp('DOM.querySelector',{nodeId:doc.nodeId,selector:'#files'});await cdp('DOM.setFileInputFiles',{nodeId,files:paths});}
try {
  fixture=spawn('python3',[path.join(root,'tests/transfer_fixture.py')],{cwd:root,stdio:['ignore','pipe','pipe']});
  const info=await new Promise((resolve,reject)=>{let output='';fixture.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});fixture.on('exit',code=>reject(new Error('Fixture exited '+code)));setTimeout(()=>reject(new Error('Fixture timeout')),5000).unref();});
  chrome=spawn('/usr/bin/google-chrome',['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+temp,'about:blank'],{stdio:'ignore'});
  let port;
  for(let i=0;i<100;i++){try{port=Number((await readFile(path.join(temp,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{}await sleep(100);}
  assert(port,'Chrome did not start');
  const tabs=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  ws=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  ws.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.id){const task=pending.get(data.id);pending.delete(data.id);if(data.error)task.reject(new Error(data.error.message));else task.resolve(data.result);}else if(data.method==='Runtime.exceptionThrown')errors.push(data.params.exceptionDetails.text);});
  await cdp('Page.enable');await cdp('Runtime.enable');
  await cdp('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await cdp('Page.navigate',{url:info.url});await wait("document.readyState==='complete' && !!document.querySelector('#dropzone')");
  await wait("getComputedStyle(document.querySelector('.library')).opacity==='1'");await sleep(450);await screenshot('desktop');
  assert.equal(await evaluate("document.querySelectorAll('.file-row').length"),6);
  assert.equal(await evaluate("document.querySelector('#file-list').textContent.includes('.env')"),false);
  assert.equal(await evaluate("document.documentElement.scrollWidth>innerWidth"),false);
  await evaluate("const search=document.querySelector('#search');search.value='Notas';search.dispatchEvent(new Event('input'));true");
  assert.equal(await evaluate("[...document.querySelectorAll('.file-row')].filter(row=>!row.hidden).length"),1);
  await evaluate("document.querySelector('#search').value='';document.querySelector('#search').dispatchEvent(new Event('input'));true");
  const one=path.join(temp,'uno.txt'),two=path.join(temp,'dos.txt'),large=path.join(temp,'grande.bin');
  await writeFile(one,'primer archivo');await writeFile(two,'segundo archivo');await writeFile(large,Buffer.alloc(1024*1024+1));
  await files([one,two]);await wait("document.querySelectorAll('.queue-row').length===2");
  await screenshot('queue');await evaluate("document.querySelector('#send').click();true");
  await wait("document.querySelectorAll('.queue-row[data-state=done]').length===2");
  assert.equal(await readFile(path.join(info.inbox,'uno.txt'),'utf8'),'primer archivo');
  assert.equal(await readFile(path.join(info.inbox,'dos.txt'),'utf8'),'segundo archivo');
  await screenshot('success');
  await evaluate("document.querySelector('#clear').click();true");await files([large]);
  await wait("document.querySelector('.queue-state').textContent==='Supera el límite'");
  assert.equal(await evaluate("document.querySelector('#send').disabled"),true);
  await evaluate("document.querySelector('#clear').click();const dt=new DataTransfer();dt.items.add(new File(['dropped'],'arrastrado.txt',{type:'text/plain'}));document.querySelector('#dropzone').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:dt}));true");
  await wait("document.querySelector('.queue-name').textContent==='arrastrado.txt'");
  await evaluate("document.querySelector('#send').click();true");await wait("document.querySelector('.queue-row').dataset.state==='done'");
  assert.equal(await readFile(path.join(info.inbox,'arrastrado.txt'),'utf8'),'dropped');
  // Simulate a server failure; the actual request never reaches the fixture.
  await cdp('Fetch.enable',{patterns:[{urlPattern:'*/api/upload',requestStage:'Request'}]});
  const intercept=event=>{const data=JSON.parse(event.data);if(data.method==='Fetch.requestPaused')cdp('Fetch.fulfillRequest',{requestId:data.params.requestId,responseCode:503,body:''});};
  ws.addEventListener('message',intercept);
  await evaluate("document.querySelector('#clear').click();true");await files([one]);await evaluate("document.querySelector('#send').click();true");
  await wait("document.querySelector('.queue-state').textContent==='Servidor ocupado'");
  assert.equal(await evaluate("document.querySelector('#send').disabled"),false);
  ws.removeEventListener('message',intercept);await cdp('Fetch.disable');
  await evaluate("document.querySelector('#send').click();true");await wait("document.querySelector('.queue-row').dataset.state==='done'");
  // Hold a request to verify cancellation and control recovery.
  await cdp('Fetch.enable',{patterns:[{urlPattern:'*/api/upload',requestStage:'Request'}]});
  await evaluate("document.querySelector('#clear').click();true");await files([two]);await evaluate("document.querySelector('#send').click();true");
  await wait("!document.querySelector('#cancel').hidden");await evaluate("document.querySelector('#cancel').click();true");
  await wait("document.querySelector('#message').textContent==='Envío cancelado.'");
  assert.equal(await evaluate("document.querySelector('#dropzone').disabled"),false);
  await cdp('Fetch.disable');
  await evaluate("document.querySelector('#clear').click();true");
  for(const width of [390,320]){
    await cdp('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:true});await sleep(200);
    assert.equal(await evaluate("document.documentElement.scrollWidth>innerWidth"),false,'Overflow at '+width);
    await screenshot('mobile-'+width);
  }
  await cdp('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await evaluate("getComputedStyle(document.querySelector('#dropzone')).transitionDuration"),'0s');
  assert.deepEqual(errors,[]);
  console.log('BROWSER_OK: desktop, mobile 390/320, search, file picker, drag/drop, uploads, oversize, retry, cancel, reduced motion; no JS exceptions.');
  console.log('PREVIEWS: '+artifacts);
} finally {
  ws?.close();chrome?.kill('SIGTERM');fixture?.kill('SIGTERM');
  await sleep(250);await rm(temp,{recursive:true,force:true});
}
