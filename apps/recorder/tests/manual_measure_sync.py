import subprocess,array,math,sys,json
from pathlib import Path
root=Path(sys.argv[1])
project=json.loads((root/'project.json').read_text())
for path in [*sorted(root.glob('segment-*.mkv')),root/'export.mp4']:
 clip=next((c for c in project['clips'] if c['source_id']==path.stem),None)
 start=clip['in_s'] if clip else 0
 end=clip['out_s'] if clip else 1000000
 v=subprocess.check_output(['ffmpeg','-v','error','-copyts','-i',str(path),'-vf',f'trim=start={start}:end={end},setpts=PTS-{start}/TB,fps=30:start_time=0,scale=1:1','-f','rawvideo','-pix_fmt','gray','-'])
 a=array.array('f',subprocess.check_output(['ffmpeg','-v','error','-copyts','-i',str(path),'-map','0:a:0','-af',f'atrim=start={start}:end={end},asetpts=PTS-{start}/TB,aresample=async=1:first_pts=0','-ac','1','-ar','48000','-f','f32le','-']))
 rms=[math.sqrt(sum(x*x for x in a[i:i+480])/480) for i in range(0,len(a)-480,480)]
 vt=[i/30 for i in range(1,len(v)) if (v[i]>128)!=(v[i-1]>128)]
 at=[i/100 for i in range(1,len(rms)) if (rms[i]>.01)!=(rms[i-1]>.01)]
 errors=[round(t-min(at,key=lambda a:abs(a-t)),3) for t in vt if at and min(abs(a-t) for a in at)<.5]
 print(path.name,'pixel range',min(v),max(v),'audio rms max',max(rms),'video transitions',vt,'audio transitions',at,'delta',errors)

 assert errors and max(abs(e) for e in errors)<=.08, (path.name,errors)
