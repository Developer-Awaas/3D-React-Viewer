import os
import sys

import pytest

# put the server/ folder on the path so `import main, perception` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Where the confidential golden corpus lives. It is gitignored and never
# committed, so a fresh checkout (or a Chakra job's repo copy) has no plans/
# PDFs at all. DRISHTI_PLANS_DIR lets a run point at wherever the real corpus
# is kept on that machine; unset, it falls back to the repo's own plans/.
PLANS_DIR = os.environ.get("DRISHTI_PLANS_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans"
)


def require_corpus_file(name):
    """Return the path to a golden-corpus PDF, or FAIL the test loudly if the
    corpus is missing. A skipped golden test reads as a pass; the gate must
    fail where it cannot run so absence is never silently green."""
    path = os.path.join(PLANS_DIR, name)
    if not os.path.exists(path):
        pytest.fail(
            f"GOLDEN CORPUS MISSING: '{name}' not found under {PLANS_DIR!r}. "
            "Set DRISHTI_PLANS_DIR to the folder holding the confidential "
            "plan corpus (gitignored, never committed) so the golden gate "
            "can actually run instead of silently skipping.",
            pytrace=False,
        )
    return path
