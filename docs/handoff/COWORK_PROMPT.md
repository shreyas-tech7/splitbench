# Prompt for Claude Cowork

Paste this into Claude Cowork.

```text
You are helping Shreyas finish the GitHub setup for his private repo shreyas-tech7/splitbench.
Do only the free steps below that can be undone. Do not make the repo public, publish a package,
enter or create any key, sign in for Shreyas or pay for anything. If a step needs any of those, stop
and list it for Shreyas.

1. Open https://github.com/shreyas-tech7/splitbench/actions. Report whether the latest CI run on
   main or on claude/project-thread-mok4pw passed, and copy the name of any failing step.
2. In the About box, set the description from docs/GITHUB_ABOUT.md and the topics from docs/topics.txt.
3. Under Settings, General, Social preview, upload docs/social-preview.png from the repo.
4. Check that a pre-release named v0.1.0-rc1 exists. Do not create a tag yourself.

When you finish, write the next Claude Code prompt for Shreyas. It must hold:
- Context: splitbench compares one agent with three team designs under the same budget.
- Complete: what you checked and set above.
- Open: the record-mode run with a free model, which needs a key that Shreyas creates.
- The resume launcher: "Read docs/build/BUILD_PROMPT.md and follow it. Resume from PROGRESS.md on
  branch claude/project-thread-mok4pw. Do not ask questions. Do not stop until every Done-means item
  is true or blocked with a fallback."
```
