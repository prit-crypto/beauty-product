"""Provider interface. Every AI backend implements the same calls.

extract()  free text (+ recent conversation) -> structured fields: area, concerns, budget, sensitivity, intents,
           referenced products, customer name, FAQ topic, browse filters, medical flag
phrase()   write the reply text from the engine's facts and the conversation; must keep every fact.
           None = use the template draft as-is
"""
from typing import Protocol


class Provider(Protocol):
    name: str

    def extract(self, text: str, lang: str, context: dict) -> dict: ...

    def classify_safety(self, text: str) -> bool | None: ...

    def phrase(self, lang: str, draft: str, facts: dict, mode: str = "rewrite", history=None) -> str | None: ...


INTENTS = ["greeting", "restart", "add_to_cart", "add_item", "remove_item", "recap", "compare", "search", "cart_status",
           "human", "premium", "cheaper", "how_to_use", "claim_question", "thanks", "bye", "question", "decline",
           "cart_remove", "cart_clear", "off_topic", "affirm", "deny", "checkout", "history", "order_cancel", "capabilities"]
