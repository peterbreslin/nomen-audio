"""Flagging service — determine if a file should be flagged for review."""

from app.models import ClassificationMatch

# Files with analysis but top confidence below this threshold get flagged (D057)
FLAGGED_THRESHOLD = 0.3


def should_flag(
    *,
    classification: list[ClassificationMatch] | None,
    category: str | None,
) -> bool:
    """Return True if the file should be flagged for review.

    A file is flagged when it has been analyzed but either:
    - has no category set (or empty string), OR
    - the top classification confidence is below FLAGGED_THRESHOLD
    """
    if classification is None or len(classification) == 0:
        return False

    if not category:
        return True

    return classification[0].confidence < FLAGGED_THRESHOLD
