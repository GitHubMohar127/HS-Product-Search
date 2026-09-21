import streamlit as st
import pandas as pd

from src.data_loader import load_product_data
from src.product_search import search_products, search_categories
from src.response_handler import get_ai_response


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Hindcon Product Assistant",
    page_icon="📘",
    layout="centered"
)


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data
def load_data():
    return load_product_data()


try:
    df = load_data()

except Exception as e:
    st.error(f"Unable to load the product dataset: {e}")
    st.stop()


# ============================================================
# HEADER
# ============================================================

st.title("📘 Hindcon Product Assistant")

st.caption(
    "Search for a Hindcon product or category to find available "
    "Technical Data Sheet (TDS) and Material Safety Data Sheet (MSDS) documents."
)


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# CLEAN DOCUMENT LINK
# ============================================================

def clean_document_link(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    unavailable_values = {
        "nan",
        "none",
        "null",
        "tbd",
        "n/a",
        "na",
        "not available",
        "not found",
        "tds not found",
        "msds not found",
        "tds unavailable",
        "msds unavailable"
    }

    if value.lower() in unavailable_values:
        return None

    if not (
        value.lower().startswith("http://")
        or value.lower().startswith("https://")
    ):
        return None

    return value


# ============================================================
# FIND CATEGORY IN USER MESSAGE
# ============================================================

def find_category_from_message(message):
    """
    Finds a category name inside a natural-language user message.

    Example:
        "show me all products in waterproofing compounds"
    can identify:
        "Waterproofing Compounds"

    This is a local check, so Gemini does not need to invent
    or provide category information.
    """

    if not message:
        return None

    message_normalized = " ".join(
        str(message).lower().split()
    )

    if "Category" not in df.columns:
        return None

    categories = []

    for value in df["Category"].dropna().astype(str):
        # A cell may contain multiple categories.
        for category in value.replace(";", ",").replace("|", ",").split(","):
            category = category.strip()

            if category and category.lower() not in [
                item.lower() for item in categories
            ]:
                categories.append(category)

    # Prefer longer category names first.
    categories.sort(key=len, reverse=True)

    for category in categories:
        category_normalized = " ".join(
            category.lower().split()
        )

        if category_normalized in message_normalized:
            return category

    return None


# ============================================================
# DISPLAY MESSAGE
# ============================================================

def display_message(message):

    role = message.get("role", "assistant")

    with st.chat_message(role):

        # ====================================================
        # USER MESSAGE
        # ====================================================

        if role == "user":
            st.markdown(message.get("content", ""))
            return

        message_type = message.get("type", "text")


        # ====================================================
        # NORMAL TEXT
        # ====================================================

        if message_type == "text":

            st.markdown(message.get("content", ""))


        # ====================================================
        # SINGLE PRODUCT
        # ====================================================

        elif message_type == "product":

            product_name = message.get(
                "product_name",
                "Product"
            )

            tds_link = message.get("tds_link")
            msds_link = message.get("msds_link")

            st.markdown(f"**📦 {product_name}**")

            col1, col2 = st.columns(2)

            # TDS
            with col1:
                if tds_link:
                    st.link_button(
                        "📄 TDS",
                        tds_link,
                        use_container_width=True
                    )
                else:
                    st.caption("TDS: Not Available")

            # MSDS
            with col2:
                if msds_link:
                    st.link_button(
                        "🛡️ MSDS",
                        msds_link,
                        use_container_width=True
                    )
                else:
                    st.caption("MSDS: Not Available")


        # ====================================================
        # CATEGORY PRODUCTS
        # ====================================================

        elif message_type == "category_products":

            st.markdown(
                message.get(
                    "content",
                    "Products found in this category:"
                )
            )

            products = message.get("products", [])

            if not products:
                st.caption("No products found in this category.")
                return

            # Use the EXACT same product design as a single product.
            # Category results are simply multiple product cards.
            for product in products:

                product_name = str(
                    product.get(
                        "Product_Name",
                        "Product"
                    )
                ).strip()

                tds_link = clean_document_link(
                    product.get("TDS_Link")
                )

                msds_link = clean_document_link(
                    product.get("MSDS_Link")
                )

                # Same design as message_type == "product"
                st.markdown(
                    f"**📦 {product_name}**"
                )

                col1, col2 = st.columns(2)

                # ------------------------------------------------
                # TDS
                # ------------------------------------------------

                with col1:

                    if tds_link:

                        st.link_button(
                            "📄 TDS",
                            tds_link,
                            use_container_width=True
                        )

                    else:

                        st.caption(
                            "TDS: Not Available"
                        )

                # ------------------------------------------------
                # MSDS
                # ------------------------------------------------

                with col2:

                    if msds_link:

                        st.link_button(
                            "🛡️ MSDS",
                            msds_link,
                            use_container_width=True
                        )

                    else:

                        st.caption(
                            "MSDS: Not Available"
                        )

        # ====================================================
        # MULTIPLE PRODUCTS
        # ====================================================

        elif message_type == "multiple_products":

            st.markdown(
                message.get(
                    "content",
                    "Multiple products found:"
                )
            )

            products = message.get("products", [])

            # Create clickable product buttons.
            for index, product_name in enumerate(
                products,
                start=1
            ):

                if st.button(
                    f"{index}. {product_name}",
                    key=f"product_select_{message.get('id', 'msg')}_{index}",
                    use_container_width=True
                ):

                    # Search the selected product directly.
                    # No Gemini call is required here.
                    selected_matches = search_products(
                        df,
                        product_name
                    )

                    if len(selected_matches) == 1:

                        selected_product = (
                            selected_matches.iloc[0]
                        )

                        selected_product_name = str(
                            selected_product.get(
                                "Product_Name",
                                product_name
                            )
                        ).strip()

                        selected_tds_link = clean_document_link(
                            selected_product.get("TDS_Link")
                        )

                        selected_msds_link = clean_document_link(
                            selected_product.get("MSDS_Link")
                        )

                        # Add selected product as a user message.
                        st.session_state.messages.append(
                            {
                                "role": "user",
                                "type": "text",
                                "content": selected_product_name
                            }
                        )

                        # Add product result.
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "type": "product",
                                "product_name": selected_product_name,
                                "tds_link": selected_tds_link,
                                "msds_link": selected_msds_link
                            }
                        )

                        st.rerun()

                    else:

                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "type": "text",
                                "content": (
                                    "Sorry, I could not uniquely "
                                    "identify that product. Please "
                                    "try searching for the full "
                                    "product name."
                                )
                            }
                        )

                        st.rerun()


# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================

for message in st.session_state.messages:
    display_message(message)


# ============================================================
# USER INPUT
# ============================================================

user_message = st.chat_input(
    "Search for a Hindcon product or category..."
)


# ============================================================
# PROCESS USER MESSAGE
# ============================================================

if user_message:

    # ========================================================
    # STEP 1: SAVE USER MESSAGE
    # ========================================================

    st.session_state.messages.append(
        {
            "role": "user",
            "type": "text",
            "content": user_message
        }
    )


    # ========================================================
    # STEP 2: ASK GEMINI TO UNDERSTAND THE MESSAGE
    # ========================================================

    ai_response = get_ai_response(user_message)


    # ========================================================
    # STEP 3: GREETING / CASUAL / INVALID
    # ========================================================

    if ai_response["type"] == "text":

        # Before accepting a text/invalid response from Gemini,
        # check whether the user message directly contains a
        # Hindcon category.
        detected_category = find_category_from_message(
            user_message
        )

        if detected_category:

            category_results = search_categories(
                df,
                detected_category
            )

            if not category_results.empty:

                category_products = (
                    category_results[
                        [
                            "Product_ID",
                            "Category",
                            "Product_Name",
                            "TDS_Link",
                            "MSDS_Link"
                        ]
                    ]
                    .fillna("")
                    .to_dict("records")
                )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "type": "category_products",
                        "category": detected_category,
                        "content": (
                            f"I found {len(category_products)} "
                            f"product(s) in this category."
                        ),
                        "products": category_products
                    }
                )

                st.rerun()

        st.session_state.messages.append(
            {
                "role": "assistant",
                "type": "text",
                "content": ai_response["message"]
            }
        )

        st.rerun()


    # ========================================================
    # STEP 4: PRODUCT / CATEGORY SEARCH
    # ========================================================

    if ai_response["type"] == "product_search":

        # Gemini extracts the actual search text.
        #
        # Example:
        # "Give me the TDS of Hind Crystel Seal"
        #
        # becomes:
        # "Hind Crystel Seal"

        search_query = ai_response.get(
            "search_query",
            user_message
        )

        if not search_query:
            search_query = user_message

        try:

            # =================================================
            # STEP 4A: CHECK EXPLICIT CATEGORY IN FULL MESSAGE
            # =================================================

            detected_category = find_category_from_message(
                user_message
            )

            if detected_category:

                category_results = search_categories(
                    df,
                    detected_category
                )

            else:

                # =================================================
                # STEP 4B: CHECK GEMINI-EXTRACTED CATEGORY QUERY
                # =================================================

                category_results = search_categories(
                    df,
                    search_query
                )


            # =================================================
            # CATEGORY FOUND
            # =================================================

            if not category_results.empty:

                if detected_category:
                    category_name = detected_category
                else:
                    category_name = str(
                        search_query
                    ).strip()

                category_products = (
                    category_results[
                        [
                            "Product_ID",
                            "Category",
                            "Product_Name",
                            "TDS_Link",
                            "MSDS_Link"
                        ]
                    ]
                    .fillna("")
                    .to_dict("records")
                )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "type": "category_products",
                        "category": category_name,
                        "content": (
                            f"I found {len(category_products)} "
                            f"product(s) in this category."
                        ),
                        "products": category_products
                    }
                )


            else:

                # =================================================
                # STEP 4C: NORMAL PRODUCT SEARCH
                # =================================================

                results = search_products(
                    df,
                    search_query
                )


                # =================================================
                # NO PRODUCT FOUND
                # =================================================

                if results.empty:

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "text",
                            "content": (
                                "Sorry, I could not find a matching "
                                "Hindcon product or category. Please "
                                "check the name or try another spelling."
                            )
                        }
                    )


                # =================================================
                # ONE PRODUCT FOUND
                # =================================================

                elif len(results) == 1:

                    product = results.iloc[0]

                    product_name = str(
                        product.get(
                            "Product_Name",
                            "Product"
                        )
                    ).strip()

                    tds_link = clean_document_link(
                        product.get("TDS_Link")
                    )

                    msds_link = clean_document_link(
                        product.get("MSDS_Link")
                    )

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "product",
                            "product_name": product_name,
                            "tds_link": tds_link,
                            "msds_link": msds_link
                        }
                    )


                # =================================================
                # MULTIPLE PRODUCTS
                # =================================================

                else:

                    product_names = (
                        results["Product_Name"]
                        .dropna()
                        .astype(str)
                        .str.strip()
                        .drop_duplicates()
                        .tolist()
                    )

                    message_id = (
                        f"multiple_{len(st.session_state.messages)}"
                    )

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "multiple_products",
                            "content": (
                                "I found multiple matching products. "
                                "Please specify the product name from "
                                "the list below."
                            ),
                            "products": product_names,
                            "id": message_id
                        }
                    )


        except Exception as error:

            print(
                "Product/category search error:",
                error
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "type": "text",
                    "content": (
                        "An error occurred while searching "
                        "for the product or category."
                    )
                }
            )


        # ====================================================
        # REFRESH
        # ====================================================

        st.rerun()
