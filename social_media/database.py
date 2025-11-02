"""Compatibility module exposing :class:`SocialMediaDatabase` within the
``social_media`` package namespace.

This allows imports like ``from social_media.database import SocialMediaDatabase``
while reusing the primary implementation defined in ``database.py`` at the
project root.
"""

from database import SocialMediaDatabase

__all__ = ["SocialMediaDatabase"]

