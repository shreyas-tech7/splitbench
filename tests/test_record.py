"""Record mode against a local fake OpenAI-compatible server. Nothing leaves the machine."""

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from helpers import first

from splitbench import models, runner
from splitbench.models import ChatModel, ReplayMiss, ScriptedModel


class _Fake(BaseHTTPRequestHandler):
    hits = 0
    fail_first = 0

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.hits += 1
        if _Fake.fail_first > 0:
            _Fake.fail_first -= 1
            self.send_response(429)
            self.end_headers()
            return
        text, _ = ScriptedModel().complete(body["messages"], body["max_tokens"])
        out = {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        }
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Fake)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    _Fake.hits = 0
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def test_record_then_replay_byte_for_byte(server, tmp_path):
    t = first(ttype="depth")
    rec = ChatModel("fake-model", server, tmp_path / "cache", mode="record")
    a, _ = runner.run_one(t, "single", rec, runner.Corpus(runner.T.load()[0]), "loose")
    hits = _Fake.hits
    files = sorted(p.read_bytes() for p in (tmp_path / "cache").iterdir())
    rep = ChatModel("fake-model", "http://127.0.0.1:9/never", tmp_path / "cache", mode="replay")
    b, _ = runner.run_one(t, "single", rep, runner.Corpus(runner.T.load()[0]), "loose")
    assert a["correct"] and b["correct"] and a["answer"] == b["answer"] and a["tokens"] == b["tokens"]
    assert _Fake.hits == hits  # replay sent nothing
    assert files == sorted(p.read_bytes() for p in (tmp_path / "cache").iterdir())


def test_replay_miss_fails_and_429_backs_off(server, tmp_path, monkeypatch):
    rep = ChatModel("fake-model", server, tmp_path / "c", mode="replay")
    with pytest.raises(ReplayMiss):
        rep.complete(
            [{"role": "system", "content": "Your role: single."}, {"role": "user", "content": "x"}], 10
        )
    _Fake.fail_first = 2
    rec = ChatModel("fake-model", server, tmp_path / "c", mode="record")
    waits = []
    monkeypatch.setattr(models.time, "sleep", waits.append)
    text, usage = rec.complete(
        [{"role": "system", "content": "Your role: single."}, {"role": "user", "content": "Task: none"}], 10
    )
    assert usage["input_tokens"] == 7 and _Fake.hits == 3 and waits == [2.0, 4.0]


def test_runner_resumes(tmp_path):
    """Broken case: a restarted study runs finished tasks again and doubles their rows."""
    model = ScriptedModel()
    runner.study(
        model, split="dev", levels=("tight",), archs=["single"], out=tmp_path, limit=2, log=lambda *a: None
    )
    runner.study(
        model,
        split="dev",
        levels=("tight",),
        archs=["single", "scratchpad"],
        out=tmp_path,
        limit=2,
        log=lambda *a: None,
    )
    rows = runner.load_runs(runner.runs_path(model.name, "dev", tmp_path))
    assert len(rows) == 4 and len({(r["task"], r["arch"]) for r in rows}) == 4


def test_resumed_study_keeps_earlier_transcripts(tmp_path):
    """Broken case: a resumed run with nothing new gzips an empty file over the transcripts."""
    model = ScriptedModel()
    quiet = {"split": "dev", "levels": ("tight",), "out": tmp_path, "limit": 2, "log": lambda *a: None}
    runner.study(model, archs=["single"], **quiet)
    runner.finish_transcripts(model.name, "dev", tmp_path)
    runner.study(model, archs=["single"], **quiet)
    runner.finish_transcripts(model.name, "dev", tmp_path)
    runner.study(model, archs=["single", "scratchpad"], **quiet)
    runner.finish_transcripts(model.name, "dev", tmp_path)
    gz = tmp_path / "transcripts" / f"{model.name}-dev.jsonl.gz"
    rows = gzip.decompress(gz.read_bytes()).decode().splitlines()
    keys = [(json.loads(r)["task"], json.loads(r)["arch"]) for r in rows]
    assert len(keys) == 4 and len(set(keys)) == 4
