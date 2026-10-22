from contextvars import ContextVar

# Set per request by middleware; read by audit writes so every audit row can be
# joined back to the request that produced it.
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
