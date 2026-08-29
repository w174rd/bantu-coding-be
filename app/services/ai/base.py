from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """A round could not be completed.

    `safe_to_display` marks messages this codebase wrote itself. A vendor SDK's
    exception text can echo the request that produced it, and the API key travels in
    that request — those stay in the log and never reach a client.
    """

    def __init__(
        self, message: str, status_code: int | None = None, *, safe_to_display: bool = False
    ):
        super().__init__(message)
        self.status_code = status_code
        self.safe_to_display = safe_to_display


class AIProvider(ABC):
    """One vendor's chat completion, reduced to what the discussion room needs.

    Deliberately narrow: a persona produces text and nothing else. No tools, no
    streaming, no vendor-specific structured-output mode — anything that only one
    of the four providers supports does not belong in this interface.
    """

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    async def chat(self, messages: list[dict], system: str | None = None) -> str: ...
