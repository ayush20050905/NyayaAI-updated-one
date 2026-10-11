from typing import List, Dict, Any

import ollama

from backend.llm.prompt import SYSTEM_PROMPT
from backend.utils.config import OLLAMA_MODEL

from backend.memory.memory import (
    add_message,
    build_history
)

MODEL = OLLAMA_MODEL

def build_context(results: List[Dict[str, Any]]) -> str:

    blocks = []

    for i, item in enumerate(results, start=1):

        meta = item["metadata"]

        blocks.append(
f"""
======================== DOCUMENT {i} ========================

LAW:
{meta.get("law", "Unknown")}

SECTION / ARTICLE:
{meta.get("section", "Unknown")}

CHAPTER:
{meta.get("chapter", "Not Available")}

TITLE:
{meta.get("title", "Not Available")}

LEGAL TEXT:

{item["document"]}

==============================================================
"""
        )

    return "\n".join(blocks)

def localize_answer(answer, language):

    if language == "English":
        return answer

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    f"Translate the supplied answer into {language}. "
                    "Preserve its meaning, legal citations, section numbers, "
                    "names, and quoted legal text verbatim. Do not add or omit facts. "
                    "Return only the translation."
                ),
            },
            {
                "role": "user",
                "content": answer,
            },
        ],
    )
    return response["message"]["content"].strip()


def generate_answer(question, retrieved_docs, language="English"):

    if not retrieved_docs:

        return "No relevant legal provisions were found."

    if len(retrieved_docs) > 2:
        context = build_context(retrieved_docs[:2])
    else:
        context = build_context(retrieved_docs)

    history = build_history()

    print("=" * 80)
    print("History Length :", len(history))
    print("Context Length :", len(context))
    print("=" * 80)

    prompt = f"""
You are given retrieved legal documents.

Use ONLY the retrieved documents.

Never use outside knowledge.

Never invent:

- Law names
- Section numbers
- Article numbers
- Punishments

If the answer is unavailable reply exactly:

I could not find sufficient information in the provided legal documents.

====================================================

PREVIOUS CONVERSATION

{history}

====================================================

RETRIEVED LEGAL DOCUMENTS

{context}

====================================================

QUESTION

{question}

====================================================

Respond in {language}. Use clear, accessible language while preserving
legal names, section numbers, citations, and quoted text verbatim.

====================================================

Return the answer in the following format:

Summary:
(A 2–3 sentence answer.)

Legal Explanation:
(Explain the provision in simple language.)

Applicable Provision:
Law:
Section / Article:
Chapter:

Supporting Quote:
(Quote one relevant sentence from the retrieved text.)

Do not include anything that is not present in the retrieved documents.
"""

    response = ollama.chat(

        model=MODEL,

        messages=[

            {

                "role": "system",

                "content": SYSTEM_PROMPT

            },

            {

                "role": "user",

                "content": prompt

            }

        ]

    )

    answer = response["message"]["content"].strip()

    add_message("User", question)

    add_message("Assistant", answer)

    return answer


if __name__ == "__main__":

    print("NyayaAI Ready")