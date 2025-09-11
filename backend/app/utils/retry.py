import asyncio
import functools
from typing import TypeVar, Callable, Any
from fastapi import HTTPException
from app.core.logging_config import get_logger

logger = get_logger("utils.retry")

T = TypeVar('T')

def retry_async(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Async retry decorator with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except HTTPException:
                    # Don't retry HTTP exceptions (400, 404, etc.)
                    raise
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts", exc_info=True)
                        break
                    
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}, retrying in {current_delay}s: {str(e)}")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator


def retry_sync(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Sync retry decorator with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts", exc_info=True)
                        break
                    
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}, retrying in {current_delay}s: {str(e)}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator