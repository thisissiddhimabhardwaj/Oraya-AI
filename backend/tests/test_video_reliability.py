from pathlib import Path
from unittest.mock import Mock
import pytest
from tests import test_api  # Initialize the suite's temporary database before app imports.
from app.services import video_jobs as video
PLAN={'title':'Flow','scenes':[{'type':'diagram_flow','heading':'Energy','narration':'Energy moves from nutrients to ATP.','bullets':['Nutrients','ATP']},{'type':'summary','heading':'Work','narration':'ATP supplies energy for cellular work.','bullets':['Work']}]}
def test_controlled_schema():
    with pytest.raises(ValueError):video.VideoScript.model_validate({'title':'x','scenes':[{'type':'python','code':'danger'}]})
def test_validation(monkeypatch,tmp_path):
    f=tmp_path/'x.mp4';f.write_bytes(b'0'*2000)
    for streams in [[],[{'codec_type':'video','codec_name':'unknown'}]]:
        monkeypatch.setattr(video,'probe',lambda p:{'streams':streams,'format':{'duration':'5'}})
        with pytest.raises(RuntimeError):video.validate_mp4(f)
    monkeypatch.setattr(video,'probe',lambda p:{'streams':[{'codec_type':'video','codec_name':'h264'}],'format':{'duration':'5'}})
    video.validate_mp4(f)
    with pytest.raises(RuntimeError):video.validate_mp4(f,expected_audio=True)
def test_subtitle_rounding():
    assert video.timestamp(59.9996)=='00:01:00,000'
    assert video.timestamp(3600.25)=='01:00:00,250'
def test_missing_renderer(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'binary',lambda _:None)
    with pytest.raises(RuntimeError,match='required'):video.render_plan(PLAN,tmp_path)
    assert not (tmp_path/'explainer.mp4').exists()
def test_cloud_model(monkeypatch,tmp_path):
    from app.services import ai
    client=Mock();op=Mock(done=True,error=None);asset=Mock()
    asset.save.side_effect=lambda p:Path(p).write_bytes(b'video')
    op.response.generated_videos=[Mock(video=asset)]
    client.models.generate_videos.return_value=op
    monkeypatch.setattr(ai,'_get_client',lambda:client)
    monkeypatch.setattr(video.settings,'cloud_video_model','configured-video-model')
    monkeypatch.setattr(video,'run',lambda args,*a:Path(args[-1]).write_bytes(b'encoded'))
    monkeypatch.setattr(video,'validate_mp4',lambda p:{'streams':[{'codec_type':'video'}]})
    assert video.render_cloud(video.VideoScript.model_validate(PLAN),tmp_path).is_file()
    assert client.models.generate_videos.call_count==2
    assert client.models.generate_videos.call_args.kwargs['model']=='configured-video-model'
def test_cloud_unconfigured(monkeypatch,tmp_path):
    from app.services import ai
    monkeypatch.setattr(ai,'_get_client',lambda:None)
    with pytest.raises(RuntimeError,match='credentials'):video.render_cloud(video.VideoScript.model_validate(PLAN),tmp_path)
