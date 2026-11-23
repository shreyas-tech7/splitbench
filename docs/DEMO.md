# Demo

A real terminal session on the build machine, on 2026-11-23, with the scripted model. Nothing here needs a key or a network. The `run` step had nothing left to do, because the study had already finished and the runner resumes.

Task T35 asks: "Who is the chief executive of the key supplier of the key supplier of Marro Works?" The single agent and the orchestrator both follow the chain, but the orchestrator pays for a plan, a worker report and a final combine call on top of the same reads.

```text
$ .venv/bin/splitbench check-frozen
frozen f88b345ab63d47f9a0409ab7fdf96ecf2ea29809258257abf7be1f043d6b74a9 
regenerated f88b345ab63d47f9a0409ab7fdf96ecf2ea29809258257abf7be1f043d6b74a9 
on disk f88b345ab63d47f9a0409ab7fdf96ecf2ea29809258257abf7be1f043d6b74a9

$ .venv/bin/splitbench oracle
oracle: 60 of 60 right

$ .venv/bin/splitbench run
0 new runs, 320 resumed, file results/runs-scripted-v1-heldout.jsonl

$ .venv/bin/splitbench readme --check
generated files are up to date

$ .venv/bin/splitbench show T35 single loose
   single model  in   198  out   17  {"tool": "search", "query": "Marro Works annual filing fiscal 2025"}
   single model  in   279  out   10  {"tool": "read_doc", "doc_id": "D193"}
   single model  in   370  out   10  {"tool": "read_doc", "doc_id": "D078"}
   single model  in   463  out   16  {"tool": "search", "query": "Grove Industries company profile"}
   single model  in   541  out   10  {"tool": "read_doc", "doc_id": "D276"}
   single model  in   628  out    6  {"answer": "Kai Kato"}
   single answer Kai Kato

$ .venv/bin/splitbench show T35 orchestrator loose
     lead state  plan
     lead model  in   245  out   32  {"plan": ["Who is the chief executive of the key supplier of the key supplier of Marro Wor ...
     lead state  dispatch
  worker1 model  in   198  out   17  {"tool": "search", "query": "Marro Works annual filing fiscal 2025"}
  worker1 model  in   280  out   10  {"tool": "read_doc", "doc_id": "D193"}
  worker1 model  in   371  out   10  {"tool": "read_doc", "doc_id": "D078"}
  worker1 model  in   464  out   16  {"tool": "search", "query": "Grove Industries company profile"}
  worker1 model  in   542  out   10  {"tool": "read_doc", "doc_id": "D276"}
  worker1 model  in   629  out   42  {"report": "The key supplier of Marro Works is Lumen Works. The key supplier of Lumen Work ...
     lead state  collect
     lead state  combine
     lead model  in   321  out    6  {"answer": "Kai Kato"}
     lead answer Kai Kato

$ .venv/bin/splitbench probe
groq https://api.groq.com/openai/v1/models curl: (56) CONNECT tunnel failed, response 403 no key
openrouter https://openrouter.ai/api/v1/models curl: (56) CONNECT tunnel failed, response 403 no key

```
