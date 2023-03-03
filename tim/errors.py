class AliasNotFoundError(Exception):
    """Exception raised when an expected index is not present in the cluster."""

    def __init__(self, alias: str, index: str) -> None:
        """Initialize exception with provided alias and index names for message."""
        self.message = f"Alias '{alias}' not associated with index {index}. Check "
        "index aliases and try again."
        super().__init__(self.message)


class BulkIndexingError(Exception):
    """Exception raised when an unexpected error is returned during bulk indexing."""

    def __init__(self, record: str, index: str, error: str) -> None:
        """Initialize exception with provided index name and error for message."""
        self.message = (
            f"Error indexing record '{record}' into index '{index}'. Details: {error}"
        )
        super().__init__(self.message)


class IndexExistsError(Exception):
    """Exception raised when attempting to create an index that is already present."""

    def __init__(self, index: str) -> None:
        """Initialize exception with provided index name for message."""
        self.message = f"Index '{index}' already exists in the cluster, cannot create."
        super().__init__(self.message)


class IndexNotFoundError(Exception):
    """Exception raised when an expected index is not present in the cluster."""

    def __init__(self, index: str) -> None:
        """Initialize exception with provided index name for message."""
        self.message = (
            f"Index '{index}' not present in cluster. Check index name and try again."
        )
        super().__init__(self.message)
