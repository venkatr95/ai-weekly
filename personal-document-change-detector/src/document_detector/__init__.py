"""Personal Document Change Detector — compare two document versions."""

from document_detector.pipeline import compare
from document_detector.schemas import ComparisonReport

__all__ = ["compare", "ComparisonReport"]
__version__ = "0.1.0"
