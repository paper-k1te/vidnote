"""Compatibility shim: vidnote was renamed to vid2note in v0.4.0."""

from vid2note import __version__
from vid2note.bilibili import BilibiliClient, BiliError, VideoId, VideoMeta
from vid2note.note import NoteOptions, build_note, filename

__all__ = [
    "__version__",
    "BilibiliClient",
    "BiliError",
    "NoteOptions",
    "VideoId",
    "VideoMeta",
    "build_note",
    "filename",
]
