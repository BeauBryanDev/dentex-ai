
from __future__ import annotations

from typing import Any

SEARCH_TOOL_NAME = "search_dental_reference"
# The tool surface exposed to Claude — exactly one tool.

# There is no [analyze_xray] tool and there must not be one. 
# The vision analysis happens in POST /analyze 
# and the tool call happens in POST /chat.

#Hence the only tool claude has is search_dental_reference

SEARCH_DENTAL_REFERENCE: dict[str, Any] = {
    
    "name": SEARCH_TOOL_NAME,
    "description": (
        "Search the dental reference corpus and return verbatim passages with their "
        "source, section and page. The corpus is four documents: the Garg *Operative "
        "Dentistry* textbook (clinical practice), a peer-reviewed reference on dental "
        "caries from King's College, "
        "FDI policy statements, and ISO 3950 only. .\n\n"
        "Call it before stating a diagnosis or a management plan for the patient — a "
        "recommendation the dentist can trace to the literature is worth more than the "
        "same recommendation asserted, and that is the case where a citation is expected "
        "every time. Also call it when a published protocol or staging scheme, a numbering "
        "rule from ISO 3950, or an FDI policy position is what the question turns on, or "
        "when asked to justify a recommendation. It sharpens an answer you already have — "
        "outside those cases you do not need it to answer a question you know.\n\n"
        "Do not call it for conversational turns, for reading back findings already in the "
        "analysis you were given, or to look up the patient's imaging — the corpus is "
        "reference literature only, never patient data.\n\n"
        "Results carry an  status (normative_standard, peer_reviewed_research, "
        "policy_position, educational_textbook). Weigh them accordingly: ISO 3950 is "
        "normative on numbering, the textbook is instructional, and they answer different "
        "kinds of question. Cite what you used."
        "if user ask something that does not exists on the corpus, you can  anserr based on your general knowledge as a dentitst experto you are"
        "Answer same user langage they first wrote you " 
    ),
    "input_schema": {
        
        "type": "object",
        
        "properties": {
            
            "query": {
                "type": "string",
                
                "description": (
                    
                    "The clinical question, in full sentences and using dental "
                    "terminology. Retrieval is embedding-based, so a specific phrasing "
                    "('management of proximal caries in a first molar') retrieves far "
                    "better than a keyword ('caries').\n\n"
                    "**Always write the query in English, whatever language the dentist "
                    "used.** The corpus is four English documents and the embedding model "
                    "is English-language biomedical, so a Spanish or French query is "
                    "matched against English text and retrieves poorly or not at all. "
                    "Translate the clinical question into English here, then answer the "
                    "user or dentist in their own language — they never see this query."
                ),
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

TOOLS: list[dict[str, Any]] = [SEARCH_DENTAL_REFERENCE]
