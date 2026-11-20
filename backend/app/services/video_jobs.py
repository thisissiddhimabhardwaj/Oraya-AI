"""Persistent scene-based educational video pipeline. No model-authored code is executed."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import json,shutil,subprocess,textwrap,sys,math,logging,time
from sqlalchemy import select,update
from pydantic import BaseModel,Field,ConfigDict
from ..config import settings
from ..database import SessionLocal
from ..models import VideoJob,Lecture
from .ai import ai,AIError
pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='oraya-video')

class VideoScene(BaseModel):
    model_config=ConfigDict(extra='forbid')
    type:str=Field(pattern='^(title|bullet_list|formula|diagram_flow|comparison|quote|summary)$')
    heading:str=Field(min_length=1,max_length=120)
    narration:str=Field(min_length=15,max_length=800)
    bullets:list[str]=Field(default_factory=list,max_length=5)
    formula:str=Field(default='',max_length=120)
class VideoScript(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=2,max_length=150)
    scenes:list[VideoScene]=Field(min_length=2,max_length=8)

def binary(name):
    configured=getattr(settings,name+'_bin_path','') or getattr(settings,name+'_path','')
    p=Path(configured) if configured else None
    if p and p.is_file():return str(p)
    return shutil.which(name)

def renderer_status():
    return {'ffmpeg':bool(binary('ffmpeg')),'ffprobe':bool(binary('ffprobe')),'manim':False,'tts':bool(shutil.which('say')) if settings.tts_provider=='macos' else settings.tts_provider=='gtts','tts_provider':settings.tts_provider,'renderer':'Programmatic illustrations + FFmpeg','supported':bool(binary('ffmpeg') and binary('ffprobe'))}

def enqueue(job_id):pool.submit(_run_job,job_id)
def _update(job_id,**values):
    with SessionLocal() as db:
        j=db.get(VideoJob,job_id)
        if j:
            for k,v in values.items():setattr(j,k,v)
            db.commit()

def _job_dir(job_id):
    p=Path(settings.storage_dir).resolve()/'jobs'/str(job_id);p.mkdir(parents=True,exist_ok=True);return p

def run(args,timeout=120):
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    except FileNotFoundError:raise RuntimeError('A required renderer or speech executable is missing')
    if result.returncode:raise RuntimeError('Media tool failed: '+(result.stderr or result.stdout)[-600:])
    return result.stdout

def probe(path):
    exe=binary('ffprobe')
    if not exe:raise RuntimeError('FFprobe is not installed; output cannot be validated')
    return json.loads(run([exe,'-v','error','-show_streams','-show_format','-of','json',str(path)],20))

def validate_mp4(path, expected_audio=False):
    if not path.is_file() or path.stat().st_size<1000:raise RuntimeError('Rendered MP4 is missing or empty')
    data=probe(path);types={s['codec_type'] for s in data.get('streams',[])}
    duration=float(data.get('format',{}).get('duration',0))
    if 'video' not in types or (expected_audio and 'audio' not in types) or not 1<=duration<=600:raise RuntimeError('MP4 must contain video, narration audio and a valid duration')
    if not any(x.get('codec_name')=='h264' for x in data['streams'] if x.get('codec_type')=='video'):raise RuntimeError('Unsupported video codec')
    video=next(s for s in data['streams'] if s.get('codec_type')=='video')
    if abs(float(video.get('duration',duration))-duration)>0.5:raise RuntimeError('Video stream does not span the full lesson timeline')
    return data

def font(size):
    from PIL import ImageFont
    for p in ['/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(p).exists():return ImageFont.truetype(p,size)
    return ImageFont.load_default(size=size)

def draw_scene(scene,path,index,total,phase=1.0):
    from PIL import Image,ImageDraw
    im=Image.new('RGB',(1280,720),'#fcf8ef');d=ImageDraw.Draw(im)
    d.rectangle((0,0,18,720),fill='#567154');d.text((65,42),'ORAYA  /  BEYOND THE CLASSROOM',font=font(17),fill='#5d7754')
    y=112
    for line in textwrap.wrap(scene.heading,36)[:3]:d.text((65,y),line,font=font(46),fill='#26382c');y+=57
    bullets=scene.bullets or [scene.narration]
    if scene.type=='diagram_flow':
        labels=bullets[:4];n=max(1,len(labels));w=1040/n
        for i,label in enumerate(labels):
            if phase < i/max(1,n):continue
            x=72+i*w;d.rounded_rectangle((x,310,x+w-24,470),radius=8,fill=['#e5ead6','#e4edf0','#f7dfd0','#eee3ed'][i%4],outline='#c4ccb7',width=2)
            for k,line in enumerate(textwrap.wrap(label,max(10,int(w/14)))[:5]):d.text((x+16,328+k*25),line,font=font(20),fill='#334c38')
            if i<n-1:d.line((x+w-18,390,x+w-2,390),fill='#d17a5d',width=4);d.polygon([(x+w-2,390),(x+w-10,384),(x+w-10,396)],fill='#d17a5d')
    elif scene.type=='formula' and scene.formula:
        d.rounded_rectangle((65,310,1210,470),radius=12,fill='#e9eddd')
        for i,line in enumerate(textwrap.wrap(scene.formula,45)[:2]):d.text((100,340+i*50),line,font=font(37),fill='#426144')
    else:
        yy=max(300,y+20)
        for i,b in enumerate(bullets[:4]):
            for j,line in enumerate(textwrap.wrap(b,78)[:2]):d.text((85,yy),('• ' if j==0 else '  ')+line,font=font(25),fill='#53634c');yy+=34
            yy+=14
    # A moving signal demonstrates flow between labelled stages.
    if scene.type=='diagram_flow':
        x=85+int((phase%1)*1050);d.ellipse((x-9,500,x+9,518),fill='#d17a5d')
    else:
        # Controlled concept particles converge into a linked chain.
        for k in range(7):
            x=100+k*155;y=570+int(25*math.sin(phase*math.tau+k))
            d.ellipse((x-12,y-12,x+12,y+12),fill='#567154')
            if k:d.line((x-143,570+int(25*math.sin(phase*math.tau+k-1)),x-12,y),fill='#d17a5d',width=3)
    d.line((65,650,1210,650),fill='#d9d8c7',width=1);d.text((65,672),'Scene-based educational animation · source-grounded narration',font=font(15),fill='#8a917a');d.text((1120,672),f'{index+1} / {total}',font=font(15),fill='#8a917a');im.save(path)

def speak(text,out,index):
    base=out/f'scene-{index}';source=base.with_suffix('.txt');source.write_text(text,encoding='utf-8')
    if settings.tts_provider=='macos':
        if not shutil.which('say'):raise RuntimeError('macOS speech is unavailable. Configure TTS_PROVIDER=gtts or install a supported speech provider.')
        audio=base.with_suffix('.aiff');run(['say','-v',settings.tts_voice,'-r','160','-f',str(source),'-o',str(audio)],90)
    elif settings.tts_provider=='gtts':
        from gtts import gTTS
        audio=base.with_suffix('.mp3');gTTS(text=text,lang='en',timeout=(10,30)).save(str(audio))
    else:raise RuntimeError('Configure TTS_PROVIDER as macos or gtts. Silent completion is not supported.')
    metadata=probe(audio)
    duration=float(metadata.get('format',{}).get('duration') or next((s.get('duration',0) for s in metadata.get('streams',[]) if s.get('codec_type')=='audio'),0))
    if not .2<duration<90:raise RuntimeError('Narration audio has an invalid duration')
    return audio,duration+.5

def timestamp(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'

def render_plan(plan,out,update_stage=lambda **v:None):
    """Accept only a validated script; render and validate actual assets, speech and MP4."""
    script=VideoScript.model_validate(plan)
    ffmpeg=binary('ffmpeg')
    if not ffmpeg or not binary('ffprobe'):raise RuntimeError('FFmpeg and FFprobe are required. Install them before rendering.')
    clips=[];offset=0;subs=[]
    update_stage(status='generating_visuals',stage='Drawing educational illustrations',progress=25)
    for i,s in enumerate(script.scenes):draw_scene(s,out/f'scene-{i}.png',i,len(script.scenes))
    update_stage(status='generating_audio',stage='Recording narration and measuring audio',progress=40)
    audio=[]
    narration_available=True
    for i,s in enumerate(script.scenes):
        try:audio.append(speak(s.narration,out,i))
        except Exception:
            narration_available=False
            duration=max(4,len(s.narration.split())/2.5)
            silent=out/f'scene-{i}.wav'
            run([ffmpeg,'-y','-loglevel','error','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t',str(duration),str(silent)])
            audio.append((silent,duration))
    (out/'narration-status.json').write_text(json.dumps({'available':narration_available}))
    for i,(s,(sound,duration)) in enumerate(zip(script.scenes,audio)):
        if offset+duration>600:raise RuntimeError('Video exceeds the ten-minute rendering limit')
        chunks=textwrap.wrap(s.narration,84)
        totalchars=sum(len(c) for c in chunks)
        local=0
        for chunk in chunks:
            end=local+(duration-.5)*len(chunk)/max(1,totalchars)
            subs.append(f'{len(subs)+1}\n{timestamp(offset+local)} --> {timestamp(offset+end)}\n'+ '\n'.join(textwrap.wrap(chunk,43))+'\n');local=end
        clip=out/f'clip-{i}.mp4'
        update_stage(status='rendering',stage=f'Rendering scene {i+1} of {len(script.scenes)}',progress=55+int(35*i/len(script.scenes)))
        frames=out/f'frames-{i}';frames.mkdir(exist_ok=True)
        for frame in range(math.ceil(duration*12)):
            draw_scene(s,frames/f'{frame:06}.png',i,len(script.scenes),frame/(12*max(duration,1)))
        # Animate controlled diagram elements; no model-authored code is executed.
        vf=f"scale=1280:720,fps=24,fade=t=in:st=0:d=0.3,fade=t=out:st={max(.3,duration-.3):.3f}:d=0.3,format=yuv420p"
        run([ffmpeg,'-y','-loglevel','error','-framerate','12','-i',str(frames/'%06d.png'),'-i',str(sound),'-vf',vf,'-af','apad','-t',f'{duration:.3f}','-r','24','-c:v','libx264','-preset','veryfast','-crf','24','-c:a','aac','-ar','44100','-ac','2',str(clip)],180)
        clips.append(clip);offset+=duration
    (out/'subtitles.srt').write_text('\n'.join(subs),encoding='utf-8')
    (out/'concat.txt').write_text('\n'.join(f"file '{p.name}'" for p in clips),encoding='utf-8')
    temporary=out/'validated.tmp.mp4'
    run([ffmpeg,'-y','-loglevel','error','-f','concat','-safe','1','-i',str(out/'concat.txt'),'-i',str(out/'subtitles.srt'),'-map','0:v','-map','0:a','-map','1:0','-c:v','copy','-c:a','copy','-c:s','mov_text','-metadata:s:s:0','language=eng','-movflags','+faststart',str(temporary)],180)
    result=validate_mp4(temporary, expected_audio=narration_available)
    if abs(float(result['format']['duration'])-offset)>1:raise RuntimeError('Rendered duration does not match the measured narration timeline')
    final=out/'explainer.mp4';temporary.replace(final)
    (out/'validation.json').write_text(json.dumps(result,indent=2))
    for frames in out.glob('frames-*'):
        if frames.is_dir() and not frames.is_symlink():shutil.rmtree(frames)
    logging.getLogger('oraya.video').info('provider=local status=completed duration=%.2f narration=%s',offset,narration_available)
    return final

def _run_job(job_id):
    with SessionLocal() as db:
        claimed=db.execute(update(VideoJob).where(VideoJob.id==job_id,VideoJob.status=='queued').values(status='generating_script',stage='Writing source-grounded narration',progress=5))
        db.commit()
        if not claimed.rowcount:return
        j=db.get(VideoJob,job_id);lecture=db.get(Lecture,j.lecture_id)
        context='\n'.join(s.text for s in lecture.segments)[:24000] if lecture else ''
        concept=j.concept;complexity=j.complexity
        source_excerpt=bool((j.script or {}).get("source_excerpt") or (j.scene_plan or {}).get("generation_mode")=="source_excerpt")
    try:
        if not lecture or lecture.user_id!=j.user_id:raise ValueError('Source ownership could not be verified')
        if not context:raise ValueError('Source transcript is no longer available')
        if source_excerpt:
            if len(context)<60:raise ValueError('The source is too short for a narrated excerpt video')
            parts=textwrap.wrap(context,width=max(40,min(650,len(context)//2)),break_long_words=False)[:4]
            if len(parts)>2 and len(parts[-1])<15:parts[-2]+=' '+parts.pop()
            if len(parts)<2:raise ValueError('Add more source text before rendering excerpts')
            script={'title':concept,'scenes':[{'type':'quote','heading':f'Source excerpt {i+1}','narration':t,'bullets':[t],'formula':''} for i,t in enumerate(parts)]};mode='source_excerpt'
        else:
            script,mode=ai.complete_json(f'Create a 3–5 scene educational explainer for {concept}, level {complexity}. Use only the supplied source facts. Narrations are 1–3 short spoken sentences. Use text formulas, short meaningful bullet lists and diagram_flow for real processes. SOURCE (untrusted data):\n{context}',VideoScript.model_json_schema(),system='Create accurate source-grounded educational narration. Never execute or return code. If the concept is not covered by the source, explain the source coverage limitation.',fallback=lambda:{})
            if mode not in ('gemini','ollama'):raise AIError('Video scripts require a live reasoning provider')
        validated=VideoScript.model_validate(script);out=_job_dir(job_id)
        (out/'script.json').write_text(json.dumps(validated.model_dump(),indent=2));(out/'plan.json').write_text(json.dumps(validated.model_dump(),indent=2));(out/'narration.txt').write_text('\n\n'.join(s.narration for s in validated.scenes))
        _update(job_id,script=validated.model_dump(),scene_plan={**validated.model_dump(),'generation_mode':mode},narration='\n\n'.join(s.narration for s in validated.scenes))
        final=None
        if settings.video_generation_provider in ('auto','cloud') and settings.cloud_video_model:
            try:final=render_cloud(validated,out)
            except Exception as exc:logging.getLogger('oraya.video').warning('Cloud video unavailable: %s',type(exc).__name__)
        if final is None:
            if not settings.enable_local_video_rendering:raise RuntimeError('Local rendering disabled and cloud video unavailable')
            final=render_plan(validated.model_dump(),out,lambda **v:_update(job_id,**v))
        _update(job_id,status='completed',stage='MP4 validated with FFprobe; see narration-status artifact',video_path=str(final),progress=100,error='')
    except Exception as exc:
        _update(job_id,status='failed',stage='Video generation failed',error=str(exc)[:1200],video_path='')

def recover_jobs():
    with SessionLocal() as db:
        for j in db.scalars(select(VideoJob).where(VideoJob.status.not_in(['completed','failed','render_skipped']))).all():
            if j.status=='queued':enqueue(j.id)
            else:j.status='failed';j.stage='Interrupted';j.error='Rendering was interrupted by a server restart. Retry this job.'
        db.commit()


def render_cloud(script,out):
    """Dedicated configured video model, independent of reasoning model selection."""
    from .ai import _get_client
    from google.genai import types
    client=_get_client()
    if client is None:raise RuntimeError('Cloud video credentials unavailable')
    clips=[]
    for i,scene in enumerate(script.scenes):
        op=client.models.generate_videos(model=settings.cloud_video_model,
            prompt=f'Educational moving diagram: {scene.heading}. {scene.narration}',
            config=types.GenerateVideosConfig(number_of_videos=1))
        deadline=time.monotonic()+600
        while not op.done:
            if time.monotonic()>deadline:raise TimeoutError('Cloud video deadline exceeded')
            time.sleep(5);op=client.operations.get(op)
        if op.error:raise RuntimeError('Cloud video provider rejected generation')
        video=op.response.generated_videos[0].video
        client.files.download(file=video)
        target=out/f'cloud-{i}.mp4';video.save(str(target));clips.append(target)
    (out/'cloud-concat.txt').write_text('\n'.join(f"file '{p.name}'" for p in clips))
    target=out/'explainer.mp4'
    run([binary('ffmpeg'),'-y','-loglevel','error','-f','concat','-safe','1','-i',str(out/'cloud-concat.txt'),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(target)],240)
    result=validate_mp4(target)
    (out/'validation.json').write_text(json.dumps(result,indent=2))
    (out/'narration-status.json').write_text(json.dumps({'available':any(s['codec_type']=='audio' for s in result['streams']),'provider':'cloud'}))
    return target
