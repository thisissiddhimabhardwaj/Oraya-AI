"""Real renderer check using an authored test script, not a fabricated AI result."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.video_jobs import render_plan,validate_mp4
out=Path('/private/tmp/oraya-premium-renderer-verification');out.mkdir(exist_ok=True)
plan={'title':'Cell biology — authored renderer fixture','scenes':[{'type':'title','heading':'A world within a cell','narration':'Cells are the basic units of life. Each structure has a role.','bullets':['Authored renderer test fixture'],'formula':''},{'type':'diagram_flow','heading':'Parts that work together','narration':'The nucleus stores instructions. Ribosomes build proteins using those instructions.','bullets':['Nucleus','Instructions','Ribosomes','Proteins'],'formula':''}]}
final=render_plan(plan,out);p=validate_mp4(final)
print(json.dumps({'file':str(final),'duration':p['format']['duration'],'streams':[s['codec_type'] for s in p['streams']],'bytes':final.stat().st_size,'origin':'authored test fixture; not live Gemini generation'},indent=2))
