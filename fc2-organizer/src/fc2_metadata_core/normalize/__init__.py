"""FC2 number normalization and validation."""

from fc2_metadata_core.normalize.fc2_number import (
    CANONICAL_FC2_PATTERN,
    MAX_FC2_DIGITS,
    MIN_FC2_DIGITS,
    FC2NumberResult,
    FC2RecognitionStatus,
    is_valid_fc2_number,
    normalize_fc2_number,
)

__all__ = [
    "FC2RecognitionStatus",
    "FC2NumberResult",
    "normalize_fc2_number",
    "is_valid_fc2_number",
    "MIN_FC2_DIGITS",
    "MAX_FC2_DIGITS",
    "CANONICAL_FC2_PATTERN",
]
