from helpers import CORPUS, TASKS

from splitbench import oracle


def test_oracle_gets_every_task_right_with_the_tools_only():
    for t in TASKS:
        ans, calls = oracle.solve(t, CORPUS)
        assert ans == t["answer"], t["id"]
        assert calls <= 40
