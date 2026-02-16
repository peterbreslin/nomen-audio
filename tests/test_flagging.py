"""Tests for flagging service."""

from app.models import ClassificationMatch
from app.services.flagging import should_flag


def _match(confidence: float) -> ClassificationMatch:
    return ClassificationMatch(
        cat_id="WATRSurf",
        category="WATER",
        subcategory="SURF",
        category_full="WATER-SURF",
        confidence=confidence,
    )


class TestShouldFlag:
    def test_no_analysis_not_flagged(self):
        assert should_flag(classification=None, category=None) is False

    def test_analyzed_no_category_flagged(self):
        assert should_flag(classification=[_match(0.8)], category=None) is True

    def test_analyzed_empty_category_flagged(self):
        assert should_flag(classification=[_match(0.8)], category="") is True

    def test_analyzed_low_confidence_flagged(self):
        assert should_flag(classification=[_match(0.2)], category="WATER") is True

    def test_analyzed_at_threshold_not_flagged(self):
        assert should_flag(classification=[_match(0.3)], category="WATER") is False

    def test_analyzed_high_confidence_with_category_not_flagged(self):
        assert should_flag(classification=[_match(0.8)], category="WATER") is False

    def test_empty_classification_not_flagged(self):
        assert should_flag(classification=[], category=None) is False
