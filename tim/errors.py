class IndexNotFoundError(Exception):
    """Exception raised when an expected index is not present in the cluster."""

    def __init__(self, index: str) -> None:
        """Initialize exception with provided index name for message."""
        self.message = (
            f"Index '{index}' not present in cluster. Check index name and try again."
        )
        super().__init__(self.message)
