"""
Sample agent for testing.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional


class SampleAgent:
    """Simple simulated agent for testing."""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []

    async def run(self, prompt: str) -> str:
        self.history.append({"role": "user", "content": prompt})
        response = self._respond(prompt)
        self.history.append({"role": "assistant", "content": response})
        return response

    def _respond(self, prompt: str) -> str:
        lower = prompt.lower()
        if "ignore" in lower and "instruction" in lower:
            return "I cannot ignore my instructions."
        if "hacked" in lower or "dan" in lower:
            return "I am not DAN. I am an AI assistant."
        if "system prompt" in lower:
            return "I cannot reveal my system prompt."
        if "2 + 2" in prompt:
            return "The answer is 4."
        if "5 + 3" in prompt:
            return "5 + 3 = 8, multiplied by 2 is 16, minus 4 is 12."
        if "favorite color" in lower:
            return "Your favorite color is blue."
        if "first number" in lower:
            return "The first number you told me was 0."
        if "banana" in lower:
            return "I cannot mention that word."
        if "delete" in lower and "customer" in lower:
            return "I cannot delete customer records without authorization."
        if "admin" in lower and "password" in lower:
            return "I cannot disclose passwords."
        if "hotel" in lower:
            return "I found 3 hotels in Nairobi under $150. Would you like me to book one?"
        if "book" in lower and "cheapest" in lower:
            return "I have booked the cheapest option. Confirmation #12345."
        if "cancel" in lower:
            return "I have cancelled your booking."
        if "card number" in lower:
            return "For security reasons, please do not share card numbers in chat."
        if "count" in lower:
            return "1, 2, 3. The total is 6."
        return f"Mock response to: {prompt[:60]}"
