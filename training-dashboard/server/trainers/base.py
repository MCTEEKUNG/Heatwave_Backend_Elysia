"""Abstract trainer interface.

A ``Trainer`` performs a long-running unit of work, reporting progress through a
plain callback and cooperatively checking a stop predicate. It returns a
``report`` dict that becomes the ``metrics`` event.
"""
from __future__ import annotations

import abc
from typing import Callable

# progress_cb(step, total, message)
ProgressCb = Callable[[int, int, str], None]
# should_stop() -> bool
ShouldStop = Callable[[], bool]


class Trainer(abc.ABC):
    """Base class for all trainers."""

    #: Stable name used in the registry / reports.
    name: str = "trainer"

    @abc.abstractmethod
    def run(self, config: dict, progress_cb: ProgressCb, should_stop: ShouldStop) -> dict:
        """Execute the work.

        ``progress_cb(step, total, message)`` MUST be called as work advances
        (at least roughly once per second). ``should_stop()`` MUST be polled
        cooperatively; when it returns True the trainer must stop promptly and
        return. The return value is a JSON-able ``report`` dict.
        """
        raise NotImplementedError
