
from __future__ import annotations

from typing import Any

# The tool surface exposed to Claude.
SEARCH_TOOL_NAME = "search_dental_reference"
DENTAL_OFFICE_TOOL_NAME = "find_dental_offices_nearby"
ORAL_HEALTH_STATS_TOOL_NAME = "get_country_oral_health_access"
ADVICE_VIDEO_TOOL_NAME = "find_oral_health_advice_videos"


# There is no [analyze_xray] tool and there must not be one. 
# The vision analysis happens in POST /analyze | vision is not a tool Claude can call. 
# The only tool Claude can call are these one below....
# These are the tools exposed to Agent loop.

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
        "GPS, or assumptions, this is invasive.\n\n"
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

GET_COUNTRY_ORAL_HEALTH_ACCESS: dict[str, Any] = {

    "name": ORAL_HEALTH_STATS_TOOL_NAME,
    "description": (
        "Look up country-level oral health *system* indicators from the WHO Global "
        "Health Observatory: whether the country has a national oral health plan, "
        "whether screening, urgent and restorative care are available in the public "
        "system, and the share of oral care covered by a government scheme.\n\n"
        "Call it when the question is about access, cost, coverage, public policy or "
        "what care a patient can expect to get in a particular country — 'is a filling "
        "covered where I live?', 'can I get urgent dental care in Colombia?'. The "
        "country must come from the user's own message; if they have not said which "
        "country, ask plainly and wait, exactly as with the dental office search. "
        "Never infer it from IP, GPS, or the language they write in.\n\n"
        "This is health-system data, never clinical guidance and never patient data: it "
        "cannot tell you how to treat a tooth. For clinical questions use "
        f"`{SEARCH_TOOL_NAME}`; for a specific clinic use "
        f"`{DENTAL_OFFICE_TOOL_NAME}`.\n\n"
        "Each indicator carries the year it was reported — say the year when you quote "
        "a figure, and say plainly when an indicator has no data rather than filling the "
        "gap from memory. WHO reports on national systems, so it describes the public "
        "system in general, not the user's own insurance. Answer in the user's language."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "country": {
                "type": "string",
                "description": (
                    "The country the user named, as they stated it (for example "
                    "'Colombia', 'France', 'Viet Nam'). English spelling resolves most "
                    "reliably. Pass a country — not a city, region or ISO code; if the "
                    "user gave only a city, use the country it is in, and ask when that "
                    "is ambiguous. Required — never invent or infer this value."
                ),
            },
        },
        "required": ["country"],
        "additionalProperties": False,
    },
}


FIND_ORAL_HEALTH_ADVICE_VIDEOS: dict[str, Any] = {

    "name": ADVICE_VIDEO_TOOL_NAME,
    "description": (
        "Find short oral health advice videos on YouTube, restricted to a small list of "
        "vetted dentist-run channels — brushing and flossing technique, interdental "
        "brushes, caring for a new crown or implant, what a procedure involves, settling "
        "a child\'s or a nervous patient\'s fear of the chair.\n\n"
        "**Call it only when the user asks for a video.** They must have asked — for a "
        "video, a demonstration, \'show me\', \'something I can watch\'. A question about a "
        "technique is not a request for a video: answer it in words. A diagnosis is "
        "never a request for a video — after reading an X-ray, give the findings and the "
        "plan and stop, and do not close with an offer of a link. If watching would "
        "genuinely help, you may offer once in a single sentence and wait; call this "
        "tool only once they have said yes.\n\n"
        "It is an adjunct, never the answer. Give your own explanation first and offer "
        "the video as something to watch afterwards. Do not call it to establish a "
        "clinical fact, to justify a recommendation, or in place of "
        f"`{SEARCH_TOOL_NAME}` — a video is not evidence, and the reference corpus is "
        "what a recommendation is grounded in.\n\n"
        "Only videos from the trusted channels are returned, so the result may be empty. "
        "That is a real answer: say nothing suitable was found and carry on with your own "
        "explanation. Never fill the gap with a YouTube link from memory — a link you "
        "invent is very likely dead or to a channel nobody vetted. Only ever give links "
        "this tool returned, as markdown links using the title and URL from its output."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "What the video should demonstrate, as a short phrase in the "
                    "`language` you are passing ('correct flossing technique', "
                    "'tecnica de cepillado para ninos'). Describe the technique or topic, "
                    "not the patient — never put findings, tooth numbers or anything else "
                    "from the X-ray into this query; it goes to YouTube."
                ),
            },
            "language": {
                "type": "string",
                "enum": ["en", "es"],
                "description": (
                    "Language of the channels to search: 'en' or 'es'. Match the "
                    "language the user is writing in. There is a trusted channel list per "
                    "language and only these two exist — for a user writing in any other "
                    "language, use 'en' and tell them the video is in English."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

# These are the tools exposed to Agent loop.
TOOLS: list[dict[str, Any]] = [
    SEARCH_DENTAL_REFERENCE,
    FIND_DENTAL_OFFICES_NEARBY,
    GET_COUNTRY_ORAL_HEALTH_ACCESS,
    FIND_ORAL_HEALTH_ADVICE_VIDEOS,
]
