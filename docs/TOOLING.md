# Tooling

What I used to build splitbench, what I checked before trusting it, and what I skipped.

| Tool | Used for | Vetted how | Result |
| --- | --- | --- | --- |
| uv | the project venv and installs | standard Astral release on the build machine | used |
| pytest | tests | pinned by pyproject dev extra | used |
| ruff | lint, format, and the `S` security rules | pinned by pyproject dev extra | used |
| gitleaks | secret scan before each commit and over the whole history | built with `go install` from the upstream module. The pre-commit hook pins v8.30.1 | used |
| pip-audit | dependency audit in the release check | PyPI package from the PyPA project | used |
| actionlint v1.7.12 | lint for `.github/workflows/ci.yml` | built with `go install` from rhysd/actionlint | used |
| superpowers skills (brainstorming, test-driven-development, systematic-debugging, verification-before-completion, requesting-code-review) | build process | already loaded in the session | used |
| `npx skills add` (ponytail and the other skills in the brief) | extra skills | the permission system denied the install | skipped, see BLOCKERS.md |
| osv-scanner, semgrep | security scans | hosts refused by the network proxy | replaced by pip-audit and `ruff --select S` |
| deskbench (shreyas-tech7/deskbench) | `scripts/check_links.py`, `scripts/make_social_preview.py`, `tests/conftest.py`, CI layout | an earlier build in the same set, read in full before copying | copied and adapted |

No runtime dependency is installed. The package uses only the Python standard library.
