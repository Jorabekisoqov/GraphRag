"""Metrics collection for monitoring."""
from prometheus_client import Counter, Histogram, Gauge
from typing import Optional, ContextManager
import time

# Query metrics
query_counter = Counter(
    'graphrag_queries_total',
    'Total number of queries processed',
    ['status']  # 'success' or 'error'
)

query_duration = Histogram(
    'graphrag_query_duration_seconds',
    'Time spent processing queries',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# API call metrics
openai_api_calls = Counter(
    'graphrag_openai_api_calls_total',
    'Total number of OpenAI API calls',
    ['operation']  # 'refine_query', 'synthesize_response'
)

neo4j_queries = Counter(
    'graphrag_neo4j_queries_total',
    'Total number of Neo4j queries',
    ['status']  # 'success' or 'error'
)

# System health metrics
neo4j_connection_status = Gauge(
    'graphrag_neo4j_connection_status',
    'Neo4j connection status (1 = healthy, 0 = unhealthy)'
)

openai_api_status = Gauge(
    'graphrag_openai_api_status',
    'OpenAI API status (1 = healthy, 0 = unhealthy)'
)


class QueryTimer(ContextManager):
    """Context manager for timing queries."""
    
    def __init__(self) -> None:
        self.start_time: Optional[float] = None
    
    def __enter__(self) -> "QueryTimer":
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> bool:
        if self.start_time:
            duration = time.time() - self.start_time
            query_duration.observe(duration)
        
        if exc_type is None:
            query_counter.labels(status='success').inc()
        else:
            query_counter.labels(status='error').inc()
        
        return False  # Don't suppress exceptions
