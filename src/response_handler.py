import os
import json
import re

from google import genai
from google.genai import types


# ============================================================
# GEMINI CLIENT
# ============================================================

def get_ai_client():
    """
    Create and return the Gemini client.

    The API key is read from the environment variable:

        GEMINI_API_KEY

    If the API key is not available, None is returned.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


# ============================================================
# BASIC TEXT HELPERS
# ============================================================

def normalize_message(message):
    """
    Normalize a user's message for simple local checks.

    Examples:

        " VMA "      -> "vma"
        "Powdar"     -> "powdar"
        "HIND"       -> "hind"
        "Hello!!!"   -> "hello"
    """

    if not isinstance(message, str):
        return ""

    message = message.lower().strip()

    # Remove extra spaces
    message = re.sub(r"\s+", " ", message)

    return message


def is_simple_product_candidate(message):
    """
    Decide whether a short/simple user message should be treated
    as a possible product search BEFORE asking Gemini.

    This is the important fix for cases such as:

        VMA
        vma
        powder
        powdar
        plast
        crystel
        seal
        hind
        sca
        wp

    We do NOT assume that the word is actually a valid product.

    We only say:

        "This looks like a possible product search."

    Python will later check the Excel dataset.

    This prevents Gemini from incorrectly saying:

        invalid

    for a short product name or abbreviation.
    """

    text = normalize_message(message)

    if not text:
        return False

    # --------------------------------------------------------
    # Known greetings should NOT become product searches
    # --------------------------------------------------------

    greetings = {
        "hi",
        "hello",
        "hey",
        "hii",
        "hiii",
        "helo",
        "good morning",
        "good afternoon",
        "good evening",
        "good night",
    }

    if text in greetings:
        return False

    # --------------------------------------------------------
    # Known casual messages should NOT become product searches
    # --------------------------------------------------------

    casual_messages = {
        "thanks",
        "thank you",
        "thankyou",
        "bye",
        "goodbye",
        "how are you",
        "how are ypu",
        "how are u",
        "how r you",
        "how r u",
        "who are you",
        "what are you",
        "what are you doing",
        "nice",
    }

    if text in casual_messages:
        return False

    # --------------------------------------------------------
    # Technical/general questions should NOT be treated as
    # simple product searches.
    # --------------------------------------------------------

    technical_starters = (
        "what is ",
        "what are ",
        "how much ",
        "how many ",
        "when should ",
        "why ",
        "where should ",
        "how do ",
        "how can ",
        "tell me about ",
        "explain ",
        "what does ",
        "can you explain ",
    )

    if text.startswith(technical_starters):
        return False

    # --------------------------------------------------------
    # Very short single-word input
    # --------------------------------------------------------
    #
    # Examples:
    #
    # VMA
    # vma
    # powder
    # powdar
    # plast
    # seal
    #
    # These should be allowed to reach Python search.
    # --------------------------------------------------------

    words = text.split()

    if len(words) == 1:

        # If it is a short word consisting mostly of letters/numbers,
        # consider it a possible product search.
        #
        # We deliberately allow unknown words here.
        # The Excel dataset decides whether a product exists.
        if re.fullmatch(r"[a-z0-9]+", text):

            return True

    return False


# ============================================================
# GEMINI MESSAGE ANALYSIS
# ============================================================

def analyze_user_message(message):
    """
    Understand the user's message.

    Gemini is used to understand natural-language requests.

    IMPORTANT:
    Gemini does NOT decide whether a product exists.

    Python + Excel are responsible for checking the actual
    product database.

    Supported intents:

        greeting
        product_search
        casual
        invalid
    """

    if not isinstance(message, str):
        message = ""

    message = message.strip()

    if not message:
        return {
            "intent": "invalid",
            "search_query": "",
            "confidence": 1.0,
            "reason": "Empty message."
        }

    normalized_message = normalize_message(message)

    # ========================================================
    # LOCAL CHECK — SIMPLE PRODUCT SEARCH
    # ========================================================
    #
    # This is the main fix for:
    #
    #     VMA
    #     vma
    #     powder
    #     powdar
    #     plast
    #
    # We do not need Gemini to classify these.
    # ========================================================

    if is_simple_product_candidate(message):

        return {
            "intent": "product_search",
            "search_query": message,
            "confidence": 1.0,
            "reason": (
                "Simple product-search candidate detected locally."
            )
        }

    # ========================================================
    # GEMINI CLIENT
    # ========================================================

    client = get_ai_client()

    if client is None:

        return {
            "intent": "error",
            "search_query": "",
            "confidence": 0.0,
            "reason": (
                "GEMINI_API_KEY was not found."
            )
        }

    # ========================================================
    # GEMINI PROMPT
    # ========================================================

    prompt = f"""
You are the message understanding system for a Hindcon
Product Assistant.

The application is used ONLY for:

1. Finding Hindcon products.
2. Finding the TDS document link for a product.
3. Finding the MSDS document link for a product.

You must NOT answer technical questions.

You must NOT invent product information.

You must NOT invent TDS or MSDS information.

Python will search the Excel database for the actual product.

Your job is ONLY to classify the user's message and,
when appropriate, extract the product search phrase.

============================================================
IMPORTANT PRODUCT SEARCH RULE
============================================================

If the user appears to be looking for a Hindcon product,
classify the message as:

product_search

This includes:

- Complete product names
- Partial product names
- Product abbreviations
- Product codes
- Product-name fragments
- Possible spelling mistakes
- Short unknown words that could be product names

Examples:

VMA
vma
powder
powdar
plast
hind
seal
crystel
crystal
proof
plug
sca
wp

These should be treated as possible product searches.

DO NOT classify a short unknown word as invalid just because
you do not recognize it.

Python will determine whether the product actually exists.

============================================================
PRODUCT SEARCH EXAMPLES
============================================================

User:
Hind Crystel Seal

intent:
product_search

search_query:
Hind Crystel Seal


User:
hind crystel sel

intent:
product_search

search_query:
hind crystel sel


User:
Give me the TDS of Hind Crystel Seal

intent:
product_search

search_query:
Hind Crystel Seal


User:
I need the MSDS of Hind Fix TA

intent:
product_search

search_query:
Hind Fix TA


User:
show me Hind Sol SR

intent:
product_search

search_query:
Hind Sol SR


User:
Hind Plast N

intent:
product_search

search_query:
Hind Plast N


User:
hind plast

intent:
product_search

search_query:
hind plast


User:
hind

intent:
product_search

search_query:
hind


User:
VMA

intent:
product_search

search_query:
VMA


User:
vma

intent:
product_search

search_query:
vma


User:
powdar

intent:
product_search

search_query:
powdar


User:
powder

intent:
product_search

search_query:
powder

============================================================
GREETING
============================================================

Classify these as greeting:

hi
hello
hey
hii
hiii
helo
good morning
good afternoon
good evening
good night

For greeting:

search_query must be empty.

============================================================
CASUAL
============================================================

Classify these as casual:

how are you
how are ypu
how are u
how r you
how r u
thanks
thank you
bye
goodbye
who are you
what are you
what are you doing
nice

For casual:

search_query must be empty.

============================================================
INVALID
============================================================

Invalid means the user is clearly asking about something
outside the Hindcon product/document search system.

Examples:

What is today's weather?
What is today's date?
Who is the Prime Minister?
Tell me a joke.
Solve this mathematics problem.
Write Python code.
What happened in cricket today?
What is football?
What is artificial intelligence?

For invalid:

search_query must be empty.

============================================================
TECHNICAL TDS QUESTIONS
============================================================

The current application does NOT answer technical questions.

Examples:

What is the setting time of Hind Plug - S?
What is the coverage of Hind Crystel Seal?
What is the shelf life of Hind Powder WP?
What is the density of Hind Fix TA?
How do I apply Hind Crystel Seal?

These should NOT be answered by Gemini.

However, if the user clearly mentions a product and asks for
its TDS/MSDS document, classify it as product_search.

Example:

Give me the TDS of Hind Crystel Seal

product_search

search_query:
Hind Crystel Seal

============================================================
IMPORTANT
============================================================

Never invent a product name.

Never answer the user's question.

Only return the classification and extracted search phrase.

Return ONLY valid JSON.

Required fields:

intent
search_query
confidence
reason

User message:
{message}
"""

    # ========================================================
    # CALL GEMINI
    # ========================================================

    try:

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",

                response_schema={
                    "type": "OBJECT",

                    "properties": {

                        "intent": {
                            "type": "STRING",

                            "enum": [
                                "greeting",
                                "product_search",
                                "casual",
                                "invalid"
                            ]
                        },

                        "search_query": {
                            "type": "STRING"
                        },

                        "confidence": {
                            "type": "NUMBER"
                        },

                        "reason": {
                            "type": "STRING"
                        }
                    },

                    "required": [
                        "intent",
                        "search_query",
                        "confidence",
                        "reason"
                    ]
                }
            )
        )

        response_text = response.text.strip()

        if not response_text:

            return {
                "intent": "error",
                "search_query": "",
                "confidence": 0.0,
                "reason": (
                    "Gemini returned an empty response."
                )
            }

        result = json.loads(response_text)

        # ----------------------------------------------------
        # Validate intent
        # ----------------------------------------------------

        valid_intents = {
            "greeting",
            "product_search",
            "casual",
            "invalid"
        }

        intent = result.get(
            "intent",
            "invalid"
        )

        if intent not in valid_intents:

            intent = "invalid"

        # ----------------------------------------------------
        # Get search query
        # ----------------------------------------------------

        search_query = result.get(
            "search_query",
            ""
        )

        if not isinstance(search_query, str):

            search_query = ""

        search_query = search_query.strip()

        # ----------------------------------------------------
        # Safety fallback
        # ----------------------------------------------------
        #
        # If Gemini says product_search but doesn't provide
        # a query, use the original user message.
        # ----------------------------------------------------

        if intent == "product_search" and not search_query:

            search_query = message

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        confidence = result.get(
            "confidence",
            0.0
        )

        try:

            confidence = float(confidence)

        except (TypeError, ValueError):

            confidence = 0.0

        confidence = max(
            0.0,
            min(1.0, confidence)
        )

        return {
            "intent": intent,
            "search_query": search_query,
            "confidence": confidence,
            "reason": result.get(
                "reason",
                "Gemini analyzed the message."
            )
        }

    except Exception as error:

        # Print the real error in PowerShell so it can be
        # diagnosed if Gemini has a quota/API/model problem.

        print(
            "Gemini error:",
            error
        )

        return {
            "intent": "error",
            "search_query": "",
            "confidence": 0.0,
            "reason": (
                "Gemini could not analyze the message."
            )
        }


# ============================================================
# MAIN AI RESPONSE
# ============================================================

def get_ai_response(message):
    """
    Convert the user's message into an application action.

    Possible response types:

        text
        product_search
    """

    result = analyze_user_message(message)

    intent = result["intent"]

    # ========================================================
    # GEMINI/API ERROR
    # ========================================================

    if intent == "error":

        # ----------------------------------------------------
        # IMPORTANT FALLBACK
        # ----------------------------------------------------
        #
        # Even if Gemini is unavailable, a simple product-like
        # search should still work.
        #
        # Example:
        #
        # Gemini quota exhausted
        # User: VMA
        #
        # We can still search Excel.
        # ----------------------------------------------------

        if is_simple_product_candidate(message):

            return {
                "type": "product_search",
                "search_query": message,
                "analysis": {
                    **result,
                    "intent": "product_search",
                    "search_query": message,
                    "reason": (
                        "Gemini unavailable; "
                        "local product-search fallback used."
                    )
                }
            }

        return {
            "type": "text",

            "message": (
                "Sorry, I am temporarily unable to "
                "understand your request. Please try again."
            ),

            "analysis": result
        }

    # ========================================================
    # GREETING
    # ========================================================

    if intent == "greeting":

        return {
            "type": "text",

            "message": (
                "Hello! How can I help you today?"
            ),

            "analysis": result
        }

    # ========================================================
    # CASUAL
    # ========================================================

    if intent == "casual":

        normalized = normalize_message(message)

        # ----------------------------------------------------
        # THANK YOU
        # ----------------------------------------------------

        if normalized in {
            "thanks",
            "thank you",
            "thankyou"
        }:

            response = (
                "You're welcome! "
                "How can I help you find a Hindcon product?"
            )

        # ----------------------------------------------------
        # GOODBYE
        # ----------------------------------------------------

        elif normalized in {
            "bye",
            "goodbye"
        }:

            response = (
                "Goodbye! Have a great day."
            )

        # ----------------------------------------------------
        # HOW ARE YOU
        # ----------------------------------------------------

        elif normalized in {
            "how are you",
            "how are ypu",
            "how are u",
            "how r you",
            "how r u"
        }:

            response = (
                "I'm doing well! "
                "How can I help you find a Hindcon product?"
            )

        # ----------------------------------------------------
        # WHO ARE YOU
        # ----------------------------------------------------

        elif normalized in {
            "who are you",
            "what are you"
        }:

            response = (
                "I'm a Hindcon Product Assistant. "
                "I can help you find Hindcon products "
                "and their TDS/MSDS documents."
            )

        # ----------------------------------------------------
        # OTHER CASUAL MESSAGE
        # ----------------------------------------------------

        else:

            response = (
                "I'm here to help you find Hindcon products "
                "and their TDS/MSDS documents."
            )

        return {
            "type": "text",
            "message": response,
            "analysis": result
        }

    # ========================================================
    # INVALID
    # ========================================================

    if intent == "invalid":

        return {
            "type": "text",

            "message": (
                "Sorry, I can only help you search for "
                "Hindcon products and their TDS/MSDS documents."
            ),

            "analysis": result
        }

    # ========================================================
    # PRODUCT SEARCH
    # ========================================================

    if intent == "product_search":

        return {
            "type": "product_search",

            "search_query": result["search_query"],

            "analysis": result
        }

    # ========================================================
    # FINAL FALLBACK
    # ========================================================

    return {
        "type": "text",

        "message": (
            "Sorry, I could not understand your request."
        ),

        "analysis": result
    }