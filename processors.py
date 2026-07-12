# Legacy wrapper for backward compatibility. Imports from the new processors package.

from processors import (
    BaseContentProcessor,
    NewsContentProcessor,
    SupermarketContentProcessor,
    ForumContentProcessor,
    get_processor,
)

__all__ = [
    "BaseContentProcessor",
    "NewsContentProcessor",
    "SupermarketContentProcessor",
    "ForumContentProcessor",
    "get_processor",
]
