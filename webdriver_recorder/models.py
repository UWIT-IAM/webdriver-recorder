import base64
import os
import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field, validator


class Image(BaseModel):
    url: str
    base64: Optional[str]
    caption: Optional[str]
    is_error: bool = False

    def save(self, root: str):
        if not self.base64:
            return
        bytes_ = base64.b64decode(self.base64.encode("UTF-8"))
        filename = os.path.join(root, self.url)
        dirname = os.path.dirname(filename)
        os.makedirs(dirname, exist_ok=True)
        with open(filename, "wb") as f:
            f.write(bytes_)


class Outcome(Enum):
    success = "success"
    failure = "failure"
    never_started = "never started"


class Timed(BaseModel):
    start_time: datetime = Field(default_factory=lambda: datetime.now())
    end_time: Optional[datetime]

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()

    def stop_timer(self):
        self.end_time = datetime.now()

    @property
    def duration(self) -> str:
        """
        Creates a human-readable minutes/seconds slug
        detailing how long the test took.

        If the duration was 129.5 seconds,
        the output would be '2m 10s'
        """
        end_time = self.end_time or datetime.now()
        minutes = 0
        seconds = (end_time - self.start_time).seconds
        if seconds > 60:
            minutes = int(seconds / 60)
            seconds = round(seconds % 60)
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    # There are several 'noqa: E821' notes below.
    # The arguments here are part of the dict() method provided by
    # pydantic, but refer to types we don't care about here. Rather
    # than unnecessarily mangle the signature of this complex
    # method, it's better to just ignore the E821 that complains
    # about it; it's "not our problem" because we didn't make
    # these signatures.
    def dict(
        self,
        *,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,  # noqa: F821
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,  # noqa: F821
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> "DictStrAny":  # noqa: F821
        result = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

        if not exclude or "duration" not in exclude:
            result["duration"] = self.duration

        return result


class TestResult(Timed):
    test_name: str
    test_id: Optional[str]  # Will be set from test_name
    pngs: List[Image] = []
    console_errors: List[str] = []
    traceback: Optional[str]
    test_description: Optional[str]
    outcome: Outcome = Outcome.never_started

    @validator("test_id", always=True)
    def populate_test_id(cls, v, values):
        test_id = re.sub(r"[^\w]", "-", values.get("test_name"))
        if test_id.endswith("-"):
            test_id = test_id[:-1]
        test_id = re.sub(r"--", "-", test_id)
        return test_id


class Report(Timed):
    outcome: Outcome = "never started"
    results: List[TestResult] = []
    arguments: Optional[str]
    title: str

    @property
    def failures(self) -> List[TestResult]:
        filter_ = filter(lambda result: (result.outcome != Outcome.success), self.results)
        return list(filter_)

    @property
    def num_failures(self) -> int:
        return len(self.failures)


class ReportResult:
    """
    A test result for passing to the report_test fixture.
    report -- a pytest test outcome
    excinfo -- exception info if there is any
    doc -- the docstring for the test if there is any
    """

    def __init__(self, report, excinfo, doc):
        self.report = report
        self.excinfo = excinfo
        self.doc = doc
