from __future__ import annotations

import pandas as pd

from complaint_triage.evaluation.queues import queue_of


def test_each_bank_has_one_queue_per_product() -> None:
    frame = pd.DataFrame(
        {
            "company": ["A", "A", "A", "B"],
            "product": ["Credit card", "Credit card", "Checking or savings account", "Credit card"],
        }
    )

    queues = queue_of(frame)

    assert queues[0] == queues[1]
    assert len(set(queues)) == 3
