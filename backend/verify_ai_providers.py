"""Explicit live provider checks; prints safe metadata only, never credentials/text.

Run from backend: python3 verify_ai_providers.py
This does not import the database or alter .env.
"""
import json
import time
import httpx
from app.config import settings
from app.services.ai import AIError, ollama_generate
from app.services.ai_quota import classify
from google.genai.errors import APIError


def main():
    results = {}
    if not settings.gemini_enabled:
        results['gemini'] = {'model':settings.gemini_primary_model,'result':'SKIPPED',
                             'reason':'No GEMINI_API_KEY configured in process environment or backend/.env'}
    else:
        started=time.monotonic()
        try:
            with httpx.Client(timeout=30) as client:
                r=client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_primary_model}:generateContent',
                    headers={'x-goog-api-key':settings.gemini_api_key},
                    json={'contents':[{'parts':[{'text':'Reply with exactly: ORAYA_GEMINI_TEST_OK'}]}],
                          'generationConfig':{'maxOutputTokens':2048}})
            entry={'model':settings.gemini_primary_model,'http_status':r.status_code,'latency_seconds':round(time.monotonic()-started,3)}
            if r.is_success:
                texts=[p.get('text','') for c in r.json().get('candidates',[]) for p in c.get('content',{}).get('parts',[]) if not p.get('thought')]
                entry.update(result='PASS' if 'ORAYA_GEMINI_TEST_OK' in ''.join(texts) else 'FAIL',generated_text_nonempty=bool(''.join(texts).strip()))
            else:
                entry.update(result='FAIL',error=classify(APIError(r.status_code,r.json(),r)).diagnostics())
            results['gemini']=entry
        except Exception as exc:
            results['gemini']={'model':settings.gemini_primary_model,'result':'FAIL','error_type':type(exc).__name__,'latency_seconds':round(time.monotonic()-started,3)}
    started=time.monotonic()
    try:
        with httpx.Client(base_url=settings.ollama_base_url,timeout=5,trust_env=False) as client:
            tags=client.get('/api/tags');tags.raise_for_status()
            installed=settings.ollama_model in {m['name'] for m in tags.json().get('models',[])}
        results['ollama']={'model':settings.ollama_model,'reachable':True,'installed':installed}
        if installed:
            text=ollama_generate('Reply with exactly: ORAYA_OLLAMA_TEST_OK',None,None,0,2048)
            results['ollama'].update(result='PASS' if 'ORAYA_OLLAMA_TEST_OK' in text else 'FAIL',generated_text_nonempty=bool(text),latency_seconds=round(time.monotonic()-started,3))
        else:
            results['ollama'].update(result='SKIPPED',reason='Requested local model is not installed')
    except Exception as exc:
        results.setdefault('ollama',{'model':settings.ollama_model,'reachable':False})
        results['ollama'].update(result='FAIL',error_type=type(exc).__name__)
    print(json.dumps(results,indent=2))
    return results


if __name__=='__main__':
    results=main()
    raise SystemExit(1 if any(v.get('result')=='FAIL' for v in results.values()) else 0)
