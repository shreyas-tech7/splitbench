# Steps only Shreyas can do

Release commit: 51acbe0fc9c91bcaac662e9d28bbb11d0e9e69fa on branch `claude/project-thread-mok4pw`.

Do them in this order.

1. **Pull request.** Open a pull request from `claude/project-thread-mok4pw` to `main` (the session page has a button for it). Read the diff. Merge with a merge commit, so the release commit stays in the history of `main`.
2. **Tag.** Create and push the tag on the release commit:
   ```bash
   git fetch origin
   git tag -a v0.1.0-rc1 51acbe0fc9c91bcaac662e9d28bbb11d0e9e69fa -m "Release candidate 1"
   git push origin v0.1.0-rc1
   ```
   Or create a pre-release with that tag on GitHub.
3. **Secret scan.** Run it once more on a fresh clone:
   ```bash
   gitleaks git -v .
   ```
4. **Actions.** Open https://github.com/shreyas-tech7/splitbench/actions and check that the CI run on the branch is green.
5. **About box and topics.** Copy the description from `docs/GITHUB_ABOUT.md` and the topics from `docs/topics.txt`.
6. **Social preview.** Upload `docs/social-preview.png` under Settings, General, Social preview.
7. **Provider key and record run.** Create a free key at Groq or OpenRouter. Put it in a local `.env` (see `.env.example`), or add it as a network secret. Then run:
   ```bash
   .venv/bin/splitbench probe
   .venv/bin/splitbench run --provider groq --mode record --split heldout
   .venv/bin/splitbench run --provider groq --mode replay --split heldout
   .venv/bin/splitbench report --model-name llama-3.1-8b-instant
   ```
   Check the provider's free limits page first. The runner resumes, so a run that hits a daily limit can continue the next day. Commit `results/cache/` so anyone can replay it.
8. **Decide on the build prompt.** Decide whether `docs/build/BUILD_PROMPT.md` stays public.
9. **Make the repo public.** Done 2026-11-26: the repo is public.
10. **Pages.** Turn on Pages from the `docs/` folder of `main`, so `docs/index.html` has an address.
11. **Pin.** Pin the repo or list it in the profile README.
12. **PyPI.** Publish `splitbench` with trusted publishing, if you want the package on PyPI. The name was free on 2026-11-23.

Human checks that the README lists as not done yet: read the code and the results, run a free model in record mode, and check the README against the result files by hand.
