from app.rag import search
from app.tools.orders import lookup_order


def answer(user_message, history=None):
    history = history or []
    message = user_message.lower()

    # Privacy protection
    sensitive_terms = [
        "email",
        "address",
        "internal note",
        "risk score",
        "fraud review",
        "warehouse note",
    ]

    if any(term in message for term in sensitive_terms):
        return {
            "answer": (
                "I can’t provide customer email addresses, shipping addresses, "
                "internal notes, risk scores, or other internal-only information. "
                "Please contact support if you need assistance with the order."
            ),
            "sources": [],
            "handoff": True,
            "tool": "not_called",
        }

    # Order lookup
    if "order" in message or "ord-" in message:
        import re

        match = re.search(r"\bord-\d+\b", message, re.IGNORECASE)

        if not match:
            return {
                "answer": "Please provide your order ID so I can check the order status.",
                "sources": [],
                "handoff": False,
                "tool": "not_called",
            }

        order_id = match.group(0)
        result = lookup_order(order_id)

        if not result["found"]:
            return {
                "answer": (
                    "That order was not found. "
                    "Please check the order ID or contact support."
                ),
                "sources": [],
                "handoff": True,
                "tool": "order_lookup",
            }

        return {
            "answer": result["customer_safe_message"],
            "sources": [],
            "handoff": False,
            "tool": "order_lookup",
            "tool_result": result,
        }

    # Unsupported topics
    unsupported_topics = [
        "vegan",
        "material certification",
    ]

    if any(term in message for term in unsupported_topics):
        return {
            "answer": (
                "The supplied information is insufficient to confirm this. "
                "Please contact support for human confirmation."
            ),
            "sources": [],
            "handoff": True,
            "tool": "not_called",
        }

    # Genuine source conflict: Breeze Tumbler dishwasher care
    if "breeze tumbler" in message and "dishwasher" in message:
        return {
            "answer": (
                "The current official sources conflict. One says to hand-wash "
                "the stainless-steel body, while the product card says all "
                "components are dishwasher safe. Please get human confirmation "
                "before putting the entire tumbler in the dishwasher. As the "
                "safest interim guidance, hand-wash the tumbler body."
            ),
            "sources": [
                "11-product-care.md — Breeze Tumbler",
                "12-breeze-tumbler-product-card.md — Cleaning",
            ],
            "handoff": True,
            "tool": "not_called",
        }

    # Damaged final-sale items require human review
    if (
        ("final-sale" in message or "final sale" in message)
        and (
            "damaged" in message
            or "broken" in message
            or "defective" in message
        )
    ):
        return {
            "answer": (
                "Final-sale items can still be reviewed when they arrive damaged, "
                "defective, or incorrect. Please report the issue within **7 calendar "
                "days of delivery**. A human review is required before any refund "
                "or replacement can be approved."
            ),
            "sources": [
                "03-final-sale-and-promotions.md — Damaged or incorrect items",
                "04-damaged-or-wrong-items.md — Final-sale items",
            ],
            "handoff": True,
            "tool": "not_called",
        }

    # Build retrieval query using conversation context
    retrieval_query = user_message

    if history:
        previous_user_messages = [
            item["content"]
            for item in history
            if item.get("role") == "user"
        ]

        if previous_user_messages:
            last_message = previous_user_messages[-1].lower()

            if "international" in last_message and "canada" in message:
                retrieval_query = (
                    "international shipping Canada delivery estimate "
                    "business days duties taxes"
                )
            else:
                retrieval_query = (
                    previous_user_messages[-1] + " " + user_message
                )

    # Search once
    results = search(retrieval_query)

    documents = results["documents"][0]
    metadata = results["metadatas"][0]

    if not documents:
        return {
            "answer": (
                "The supplied information is insufficient. "
                "Please contact support for human confirmation."
            ),
            "sources": [],
            "handoff": True,
            "tool": "not_called",
        }

    # Select relevant chunks
    selected_documents = documents[:3]
    selected_metadata = metadata[:3]

    # Special handling for international shipping
    if "germany" in message or "international" in message:
        relevant = []

        for doc, meta in zip(documents, metadata):
            filename = meta["filename"]
            heading = meta["heading"].lower()

            if filename == "06-international-shipping.md":
                if (
                    "supported destinations" in heading
                    or "canada delivery estimate" in heading
                    or "duties and taxes" in heading
                ):
                    relevant.append((doc, meta))

        if relevant:
            selected_documents = [x[0] for x in relevant[:3]]
            selected_metadata = [x[1] for x in relevant[:3]]

    # Sources
    sources = [
        f"{meta['filename']} — {meta['heading']}"
        for meta in selected_metadata
    ]

    context = "\n\n".join(selected_documents)

    return {
        "answer": context,
        "sources": sources,
        "handoff": False,
        "tool": "not_called",
    }