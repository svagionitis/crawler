from .base import BaseContentProcessor
from .news import NewsContentProcessor
from .supermarket import SupermarketContentProcessor
from .forum import ForumContentProcessor


def get_processor(processor_type: str) -> BaseContentProcessor:
    """Registry factory to return content processors based on a configuration string."""
    registry = {
        "news": NewsContentProcessor,
        "supermarket": SupermarketContentProcessor,
        "forum": ForumContentProcessor,
    }
    normalized = (processor_type or "news").strip().lower()
    if normalized not in registry:
        raise ValueError(
            f"Unknown processor type '{processor_type}'. Available options: {list(registry.keys())}"
        )
    return registry[normalized]()
