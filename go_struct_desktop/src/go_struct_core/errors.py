class ModelValidationError(ValueError):
    """Raised when a legacy model cannot safely be analysed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid frame model: " + "; ".join(errors))
