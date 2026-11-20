"""Compatibility entry point for the modular synchronous exam service."""

from src.exam_generator.orchestration.exam_service import ExamService


class QwenExamGenerator(ExamService):
    """Preserves the existing dependency-injection contract and import path."""
