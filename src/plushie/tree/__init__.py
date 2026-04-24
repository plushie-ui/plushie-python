"""Tree normalization, diffing, and search/query helpers."""

from plushie.tree._types import Node, PatchOp, WireEncodable
from plushie.tree.diff import diff
from plushie.tree.normalize import (
    ScopedId,
    expand_rows,
    normalize,
    normalize_view,
)
from plushie.tree.search import exists, find, find_all, ids, text_of

__all__ = [
    "Node",
    "PatchOp",
    "ScopedId",
    "WireEncodable",
    "diff",
    "exists",
    "expand_rows",
    "find",
    "find_all",
    "ids",
    "normalize",
    "normalize_view",
    "text_of",
]
