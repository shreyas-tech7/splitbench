# Proposals

Ideas that are not built yet.

- **A free-model run.** Record one free model on the held-out tasks, at both budgets, then commit the cache so anyone can replay it.
- **A hybrid design.** Workers only read and report facts, and one writer composes the answer. Cognition reports that this pattern works. It needs a new entry in `agents.ARCHS` and the same budget tests.
- **Messier documents.** Put two facts in some sentences and add near duplicate companies, so search and reading get harder.
- **A noisy scripted model.** A model that misreads a fact at a fixed rate would show whether a checker earns its cost. The rate would need a source, not a guess.
