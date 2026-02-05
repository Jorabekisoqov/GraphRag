"""Rate limiting for Telegram bot."""
import time
from collections import defaultdict
from typing import Dict, Tuple, List


class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    Tracks requests per user and enforces rate limits.
    """
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed per window.
            window_seconds: Time window in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[int, List[float]] = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if a request from a user is allowed.
        
        Args:
            user_id: The Telegram user ID.
            
        Returns:
            Tuple of (is_allowed, message). If allowed, message is empty.
        """
        current_time = time.time()
        user_requests = self._requests[user_id]
        
        # Remove requests outside the time window
        user_requests[:] = [req_time for req_time in user_requests 
                          if current_time - req_time < self.window_seconds]
        
        # Check if limit exceeded
        if len(user_requests) >= self.max_requests:
            oldest_request = min(user_requests)
            wait_time = int(self.window_seconds - (current_time - oldest_request))
            return False, f"Rate limit exceeded. Please wait {wait_time} seconds before trying again."
        
        # Add current request
        user_requests.append(current_time)
        return True, ""
    
    def reset_user(self, user_id: int):
        """
        Reset rate limit for a specific user.
        
        Args:
            user_id: The Telegram user ID to reset.
        """
        if user_id in self._requests:
            del self._requests[user_id]


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
