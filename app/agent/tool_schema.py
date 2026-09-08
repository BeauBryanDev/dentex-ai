
from __future__ import annotations

from typing import Any

SEARCH_TOOL_NAME = "search_dental_reference"
DENTAL_OFFICE_TOOL_NAME = "find_dental_offices_nearby"
# The tool surface exposed to Claude.

# There is no [analyze_xray] tool and there must not be one. 
# The vision analysis happens in POST /analyze | vision is not a tool Claude can call. 
# The only tool Claude can call is search_dental_reference,
# which is a retrieval over the reference corpus.
# and the tool call happens in POST /chat.

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

FIND_DENTAL_OFFICES_NEARBY: dict[str, Any] = {
    
    "name": DENTAL_OFFICE_TOOL_NAME,
    "description": (
        "Search Google Maps for dental offices and clinics near a town or city the "
        "user has told you.\n\n"
        "**Ask first — never guess location.** Before calling this tool you must have "
        "the user's town or city from their own message. If they have not said where "
        "they are, ask plainly: 'Which town or city are you in?' Do not call this tool "
        "until they answer. Never infer location from IP address, browser geolocation, "
        "GPS, or assumptions.\n\n"
        "Use it when someone wants to find a dentist, dental clinic, or dental office "
        "near them, or asks where they can book an appointment locally. If the city "
        "name is ambiguous (for example 'Springfield'), ask which country or region they "
        "mean and pass that as region_hint.\n\n"
        "Summarise the results in the user's language. These are third-party listings — "
        "tell them to confirm hours, insurance, and availability before booking.\n\n"
        "When you mention an office in your reply, include its Google Maps link as a "
        "markdown link using the map URL from the tool output."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": (
                    "The town or city the user gave you, exactly as they stated it "
                    "(for example 'Lyon', 'Austin', 'Mexico City'). Required — do not "
                    "invent or infer this value."
                ),
            },
            "region_hint": {
                "type": "string",
                "description": (
                    "Optional country, state, or province to disambiguate the city "
                    "(for example 'France', 'Texas', 'Ontario'). Omit when the city "
                    "is already unambiguous."
                ),
            },
        },
        "required": ["city"],
        "additionalProperties": False,
    },
}

TOOLS: list[dict[str, Any]] = [SEARCH_DENTAL_REFERENCE, FIND_DENTAL_OFFICES_NEARBY]
