"""Project-specific exceptions raised by the bench, its models and its configuration."""


class MiniHilBenchError(Exception):
    """Base class for all errors raised by mini-hil-bench."""


class BenchConfigError(MiniHilBenchError):
    """Raised when a bench configuration is missing, malformed or inconsistent."""


class SignalNotFoundError(MiniHilBenchError):
    """Raised when a CAN message, CAN signal or logical bench variable does not exist."""


class FaultConfigError(MiniHilBenchError):
    """Raised when a fault definition is inconsistent (e.g. OFFSET without a signal)."""


class BenchStateError(MiniHilBenchError):
    """Raised when a bench operation is called in the wrong lifecycle state."""
