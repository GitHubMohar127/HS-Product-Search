import re
import pandas as pd

from rapidfuzz import fuzz


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """
    Convert text into a clean and consistent search format.

    This function handles product names from the Hindcon dataset.

    Examples:

        "Hind Powder WP"
            -> "hind powder wp"

        "HIND POWDER WP"
            -> "hind powder wp"

        "Hind-Powder WP"
            -> "hind powder wp"

        "Hind Powder-WP"
            -> "hind powder wp"

        "Hind Proof No – 1"
            -> "hind proof no 1"

        "Hind Sealant.PPU"
            -> "hind sealant ppu"

        "Hind Plast Super SCA-800"
            -> "hind plast super sca 800"

        "Hind Fix TA (L)"
            -> "hind fix ta l"

    Why this is required:

    The Excel file contains different punctuation styles,
    hyphens, brackets, uppercase letters and special dash
    characters. Normalizing the text allows the search system
    to compare product names consistently.
    """

    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    text = text.lower()

    # Replace special dash characters with spaces
    text = text.replace("–", " ")
    text = text.replace("—", " ")
    text = text.replace("−", " ")

    # Replace common punctuation with spaces
    text = text.replace("-", " ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")
    text = text.replace(".", " ")
    text = text.replace(",", " ")
    text = text.replace("(", " ")
    text = text.replace(")", " ")
    text = text.replace("[", " ")
    text = text.replace("]", " ")
    text = text.replace("&", " and ")

    # Keep only English letters, numbers and spaces
    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    # Remove extra spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def get_words(text):
    """
    Split text into individual normalized words.

    Examples:

        "Hind Powder WP"
            -> ["hind", "powder", "wp"]

        "Hind Plast Super SCA-800"
            -> ["hind", "plast", "super", "sca", "800"]

        "Hind Fix TA – 1"
            -> ["hind", "fix", "ta", "1"]
    """

    normalized_text = normalize_text(text)

    if not normalized_text:
        return []

    return normalized_text.split()


def compact_text(text):
    """
    Remove spaces from normalized text.

    This helps match product codes written in different ways.

    Examples:

        "SCA-800"
            -> "sca800"

        "SCA 800"
            -> "sca800"

        "Fix TA 1"
            -> "fixta1"
    """

    return normalize_text(text).replace(" ", "")


# ============================================================
# WORD MATCHING
# ============================================================

def calculate_word_score(query_word, product_word):
    """
    Compare one search word with one product-name word.

    This function supports:

    1. Exact word matching
    2. Prefix matching
    3. Partial matching
    4. Fuzzy spelling matching

    Examples from the Hindcon dataset:

        powder vs powder
            -> 100

        powdar vs powder
            -> high score

        crystel vs crystal
            -> high score

        seal vs sealant
            -> high score

        sca800 vs sca
            -> partial/fuzzy score

        800 vs 800
            -> 100
    """

    if not query_word or not product_word:
        return 0

    query_word = normalize_text(query_word).replace(" ", "")
    product_word = normalize_text(product_word).replace(" ", "")

    if not query_word or not product_word:
        return 0

    # Exact match
    if query_word == product_word:
        return 100

    # The product word starts with the search word
    #
    # Example:
    # seal -> sealant
    # pow -> powder
    if product_word.startswith(query_word):
        return 96

    # The search word starts with the product word
    #
    # Example:
    # powderwp -> powder
    if query_word.startswith(product_word):
        return 92

    # Search word appears inside product word
    #
    # Example:
    # cryst -> crystel
    if query_word in product_word:
        return 94

    # Product word appears inside search word
    if product_word in query_word:
        return 90

    # Fuzzy comparison
    ratio_score = fuzz.ratio(
        query_word,
        product_word
    )

    partial_score = fuzz.partial_ratio(
        query_word,
        product_word
    )

    WRatio_score = fuzz.WRatio(
        query_word,
        product_word
    )

    return max(
        ratio_score,
        partial_score,
        WRatio_score
    )


# ============================================================
# PRODUCT SCORE
# ============================================================

def calculate_product_score(query, product_name):
    """
    Calculate how closely a complete product name matches
    the user's search query.

    This function compares individual words instead of only
    comparing the complete product name.

    This is important because users may search using only
    part of a product name.

    Examples from the actual Hindcon dataset:

    ------------------------------------------------------------
    Example 1: Spelling mistake
    ------------------------------------------------------------

        User query:
            "powdar"

        Product name:
            "Hind Powder WP"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 2: Correct partial word
    ------------------------------------------------------------

        User query:
            "powder"

        Product name:
            "Hind Powder WP"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 3: Multiple words with spelling mistake
    ------------------------------------------------------------

        User query:
            "hind powdar"

        Product name:
            "Hind Powder WP"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 4: Product spelling variation
    ------------------------------------------------------------

        User query:
            "hind crystal seal"

        Product name:
            "Hind Crystel Seal"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 5: Product code with hyphen
    ------------------------------------------------------------

        User query:
            "sca 800"

        Product name:
            "Hind Plast Super SCA-800"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 6: Product code without space
    ------------------------------------------------------------

        User query:
            "sca800"

        Product name:
            "Hind Plast Super SCA-800"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 7: Product number
    ------------------------------------------------------------

        User query:
            "fix ta 1"

        Product name:
            "Hind Fix TA – 1"

        Expected result:
            Strong match

    ------------------------------------------------------------
    Example 8: Product name fragment
    ------------------------------------------------------------

        User query:
            "sealant"

        Product name:
            "Hind Sealant PU 160"

        Expected result:
            Strong match
    """

    query_words = get_words(query)
    product_words = get_words(product_name)

    if not query_words or not product_words:
        return 0

    # --------------------------------------------------------
    # Compare compact versions first
    # --------------------------------------------------------
    #
    # This helps with:
    #
    # sca800 vs sca-800
    # fixta1 vs fix ta 1
    #
    # --------------------------------------------------------

    compact_query = compact_text(query)
    compact_product = compact_text(product_name)

    compact_score = fuzz.partial_ratio(
        compact_query,
        compact_product
    )

    # --------------------------------------------------------
    # Compare every query word against product words
    # --------------------------------------------------------

    individual_word_scores = []

    for query_word in query_words:

        best_word_score = 0

        for product_word in product_words:

            current_score = calculate_word_score(
                query_word,
                product_word
            )

            if current_score > best_word_score:
                best_word_score = current_score

        individual_word_scores.append(
            best_word_score
        )

    if not individual_word_scores:
        return 0

    average_word_score = (
        sum(individual_word_scores)
        / len(individual_word_scores)
    )

    minimum_word_score = min(
        individual_word_scores
    )

    # --------------------------------------------------------
    # Compare the full text
    # --------------------------------------------------------

    normalized_query = normalize_text(query)
    normalized_product = normalize_text(product_name)

    full_ratio = fuzz.ratio(
        normalized_query,
        normalized_product
    )

    full_partial_ratio = fuzz.partial_ratio(
        normalized_query,
        normalized_product
    )

    token_ratio = fuzz.token_set_ratio(
        normalized_query,
        normalized_product
    )

    full_text_score = max(
        full_ratio,
        full_partial_ratio,
        token_ratio
    )

    # --------------------------------------------------------
    # Combine the scores
    # --------------------------------------------------------

    word_score = (
        average_word_score * 0.55
        + minimum_word_score * 0.20
        + full_text_score * 0.15
        + compact_score * 0.10
    )

    return word_score


# ============================================================
# SEARCH FUNCTION
# ============================================================

def search_products(
    df,
    query,
    fuzzy_threshold=78
):
    """
    Search the Hindcon product dataset.

    The search is performed in the following order:

    ------------------------------------------------------------
    STEP 1: Validate the input
    ------------------------------------------------------------

    Empty searches return no products.

    ------------------------------------------------------------
    STEP 2: Exact product-name matching
    ------------------------------------------------------------

    Example:

        "Hind Powder WP"

    Matches:

        "Hind Powder WP"

    ------------------------------------------------------------
    STEP 3: Direct partial matching
    ------------------------------------------------------------

    Example:

        "powder"

    Matches:

        "Hind Powder WP"

    Example:

        "hind plast"

    Matches products such as:

        "Hind Plast AEA"
        "Hind Plast AEP"
        "Hind Plast IWA"
        "Hind Plast N"
        "Hind Plast Super"
        "Hind Plast Super M"

    ------------------------------------------------------------
    STEP 4: Compact matching
    ------------------------------------------------------------

    Handles punctuation and spacing differences.

    Examples:

        "sca800"
            -> "Hind Plast Super SCA-800"

        "fixta1"
            -> "Hind Fix TA – 1"

    ------------------------------------------------------------
    STEP 5: Word-level fuzzy matching
    ------------------------------------------------------------

    Handles spelling mistakes.

    Examples:

        "powdar"
            -> "Hind Powder WP"

        "crystel"
            -> "Hind Crystel Seal"

        "crystal"
            -> "Hind Crystal Seal"

        "seel"
            -> possible seal-related products

        "hydroflex"
            -> HydroFlex-related products

    ------------------------------------------------------------
    STEP 6: Full-name fuzzy matching
    ------------------------------------------------------------

    Used when the previous search methods do not find a result.

    ------------------------------------------------------------
    Important safety behavior
    ------------------------------------------------------------

    Very short searches such as "a", "p", or "x" should not
    match hundreds of products accidentally.

    For short queries, a stricter matching rule is used.
    """
  
    # ========================================================
    # STEP 1 — Validate input
    # ========================================================

    if df is None or df.empty:
        if df is None:
            return pd.DataFrame()

        return pd.DataFrame(
            columns=df.columns
        )

    if not isinstance(query, str):
        return pd.DataFrame(
            columns=df.columns
        )

    query = query.strip()

    if not query:
        return pd.DataFrame(
            columns=df.columns
        )

    normalized_query = normalize_text(query)

    if not normalized_query:
        return pd.DataFrame(
            columns=df.columns
        )

    # ========================================================
    # STEP 2 — Prepare product names
    # ========================================================

    search_df = df.copy()

    if "Product_Name" not in search_df.columns:
        raise ValueError(
            "The dataset must contain a Product_Name column."
        )

    search_df["_normalized_name"] = (
        search_df["Product_Name"]
        .fillna("")
        .astype(str)
        .apply(normalize_text)
    )

    search_df["_compact_name"] = (
        search_df["Product_Name"]
        .fillna("")
        .astype(str)
        .apply(compact_text)
    )

    search_df = search_df[
        search_df["_normalized_name"] != ""
    ].copy()

    if search_df.empty:
        return pd.DataFrame(
            columns=df.columns
        )

    # ========================================================
    # STEP 3 — Exact product-name match
    # ========================================================

    exact_matches = search_df[
        search_df["_normalized_name"] == normalized_query
    ].copy()

    if not exact_matches.empty:

        exact_matches = exact_matches.drop_duplicates(
            subset=["_normalized_name"],
            keep="first"
        )

        return exact_matches.drop(
            columns=[
                "_normalized_name",
                "_compact_name"
            ],
            errors="ignore"
        ).reset_index(drop=True)

    # ========================================================
    # STEP 4 — Direct partial product-name match
    # ========================================================

    partial_matches = search_df[
        search_df["_normalized_name"].str.contains(
            normalized_query,
            regex=False,
            na=False
        )
    ].copy()

    if not partial_matches.empty:

        partial_matches = partial_matches.drop_duplicates(
            subset=["_normalized_name"],
            keep="first"
        )

        return partial_matches.drop(
            columns=[
                "_normalized_name",
                "_compact_name"
            ],
            errors="ignore"
        ).reset_index(drop=True)

    # ========================================================
    # STEP 5 — Compact matching
    # ========================================================
    #
    # This handles:
    #
    # sca800 -> sca-800
    # fixta1 -> fix ta 1
    #
    # ========================================================

    compact_query = compact_text(query)

    compact_matches = search_df[
        search_df["_compact_name"].str.contains(
            compact_query,
            regex=False,
            na=False
        )
    ].copy()

    if not compact_matches.empty:

        compact_matches = compact_matches.drop_duplicates(
            subset=["_normalized_name"],
            keep="first"
        )

        return compact_matches.drop(
            columns=[
                "_normalized_name",
                "_compact_name"
            ],
            errors="ignore"
        ).reset_index(drop=True)

    # ========================================================
    # STEP 6 — Word-level matching
    # ========================================================

    query_words = get_words(query)

    word_matches = []

    # Use a stricter rule for very short queries
    if len(normalized_query) <= 2:
        word_threshold = 98
    elif len(normalized_query) <= 3:
        word_threshold = 94
    elif len(normalized_query) <= 5:
        word_threshold = 84
    else:
        word_threshold = fuzzy_threshold

    for index, row in search_df.iterrows():

        product_name = row["_normalized_name"]

        product_words = get_words(
            product_name
        )

        if not product_words:
            continue

        query_word_scores = []

        for query_word in query_words:

            best_score = 0

            for product_word in product_words:

                current_score = calculate_word_score(
                    query_word,
                    product_word
                )

                best_score = max(
                    best_score,
                    current_score
                )

            query_word_scores.append(
                best_score
            )

        if not query_word_scores:
            continue

        minimum_score = min(
            query_word_scores
        )

        average_score = (
            sum(query_word_scores)
            / len(query_word_scores)
        )

        # Every search word must match reasonably well
        if minimum_score >= word_threshold:

            final_score = (
                average_score * 0.70
                + minimum_score * 0.30
            )

            word_matches.append(
                (index, final_score)
            )

    if word_matches:

        word_df = search_df.loc[
            [item[0] for item in word_matches]
        ].copy()

        score_map = {
            index: score
            for index, score in word_matches
        }

        word_df["_match_score"] = (
            word_df.index.map(score_map)
        )

        word_df = word_df.sort_values(
            by="_match_score",
            ascending=False
        )

        word_df = word_df.drop_duplicates(
            subset=["_normalized_name"],
            keep="first"
        )

        return word_df.drop(
            columns=[
                "_normalized_name",
                "_compact_name",
                "_match_score"
            ],
            errors="ignore"
        ).reset_index(drop=True)

    # ========================================================
    # STEP 7 — Full-name fuzzy matching
    # ======================================================== 

    fuzzy_matches = []

    for index, row in search_df.iterrows():

        product_name = row["_normalized_name"]

        if not product_name:
            continue

        ratio_score = fuzz.ratio(
            normalized_query,
            product_name
        )

        partial_score = fuzz.partial_ratio(
            normalized_query,
            product_name
        )

        token_score = fuzz.token_set_ratio(
            normalized_query,
            product_name
        )

        full_score = max(
            ratio_score,
            partial_score,
            token_score
        )

        # Stronger requirements for short queries
        if len(normalized_query) <= 3:
            required_score = 96
        elif len(normalized_query) <= 5:
            required_score = 90
        elif len(normalized_query) <= 10:
            required_score = 84
        else:
            required_score = fuzzy_threshold

        if full_score >= required_score:

            fuzzy_matches.append(
                (index, full_score)
            )

    # ========================================================
    # STEP 8 — No result
    # ========================================================

    if not fuzzy_matches:

        return pd.DataFrame(
            columns=df.columns
        )

    # ========================================================
    # STEP 9 — Return fuzzy results
    # ========================================================

    fuzzy_df = search_df.loc[
        [item[0] for item in fuzzy_matches]
    ].copy()

    score_map = {
        index: score
        for index, score in fuzzy_matches
    }

    fuzzy_df["_match_score"] = (
        fuzzy_df.index.map(score_map)
    )

    fuzzy_df = fuzzy_df.sort_values(
        by="_match_score",
        ascending=False
    )

    fuzzy_df = fuzzy_df.drop_duplicates(
        subset=["_normalized_name"],
        keep="first"
    )

    return fuzzy_df.drop(
        columns=[
            "_normalized_name",
            "_compact_name",
            "_match_score"
        ],
        errors="ignore"
    ).reset_index(drop=True)

# ============================================================
# CATEGORY SEARCH SUPPORT
# ============================================================

def _split_categories(category_value):
    """
    Convert a Category cell into individual category names.

    This handles datasets where multiple categories are stored:

        in separate rows, or
        inside one cell separated by commas, semicolons, |, /, or new lines.
    """

    if category_value is None or pd.isna(category_value):
        return []

    text = str(category_value).strip()

    if not text:
        return []

    parts = re.split(r"[,;|/\n]+", text)

    categories = []

    for part in parts:
        part = part.strip()
        if part:
            categories.append(part)

    return categories


def calculate_category_score(query, category):
    """
    Calculate the similarity between a user category search and
    one category name.

    Supports:
        - exact category matching
        - partial category matching
        - word matching
        - spelling mistakes

    Examples:
        "Waterproofing Compounds"
        "waterproofing"
        "waterprofing"
    """

    query_normalized = normalize_text(query)
    category_normalized = normalize_text(category)

    if not query_normalized or not category_normalized:
        return 0

    if query_normalized == category_normalized:
        return 100

    if query_normalized in category_normalized:
        return 96

    if category_normalized in query_normalized:
        return 94

    query_words = get_words(query_normalized)
    category_words = get_words(category_normalized)

    if not query_words or not category_words:
        return 0

    word_scores = []

    for query_word in query_words:
        best_score = 0

        for category_word in category_words:
            score = calculate_word_score(
                query_word,
                category_word
            )
            best_score = max(best_score, score)

        word_scores.append(best_score)

    if not word_scores:
        return 0

    average_score = sum(word_scores) / len(word_scores)
    minimum_score = min(word_scores)

    full_score = max(
        fuzz.ratio(query_normalized, category_normalized),
        fuzz.partial_ratio(query_normalized, category_normalized),
        fuzz.token_set_ratio(query_normalized, category_normalized)
    )

    return max(
        full_score,
        average_score * 0.65 + minimum_score * 0.35
    )


def _clean_category_results(results):
    """
    Deduplicate category results by product.

    A product may belong to more than one category, so the same
    product can occur on multiple rows. It must appear only once
    in the final category result.

    When duplicate rows exist, TDS/MSDS links are preserved if
    they are available on any row for that product.
    """

    if results is None or results.empty:
        return pd.DataFrame()

    results = results.copy()

    if "Product_Name" not in results.columns:
        return results.reset_index(drop=True)

    results["Product_Name"] = (
        results["Product_Name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    results = results[results["Product_Name"] != ""].copy()

    if results.empty:
        return results.reset_index(drop=True)

    # Use Product_ID when available because the same product name
    # can legitimately appear with different IDs in some datasets.
    if "Product_ID" in results.columns:
        group_columns = ["Product_ID"]
    else:
        group_columns = ["Product_Name"]

    output_rows = []

    for _, group in results.groupby(
        group_columns,
        sort=False,
        dropna=False
    ):
        first_row = group.iloc[0].copy()

        # Combine categories without duplicates.
        if "Category" in group.columns:
            all_categories = []

            for value in group["Category"].tolist():
                for category in _split_categories(value):
                    if normalize_text(category) not in {
                        normalize_text(x) for x in all_categories
                    }:
                        all_categories.append(category)

            first_row["Category"] = ", ".join(all_categories)

        # Preserve the first available TDS link.
        if "TDS_Link" in group.columns:
            for value in group["TDS_Link"].tolist():
                if pd.notna(value) and str(value).strip().lower() not in {"", "nan", "none"}:
                    first_row["TDS_Link"] = str(value).strip()
                    break

        # Preserve the first available MSDS link.
        if "MSDS_Link" in group.columns:
            for value in group["MSDS_Link"].tolist():
                if pd.notna(value) and str(value).strip().lower() not in {"", "nan", "none"}:
                    first_row["MSDS_Link"] = str(value).strip()
                    break

        output_rows.append(first_row)

    return pd.DataFrame(output_rows, columns=results.columns).reset_index(drop=True)


def search_categories(df, query, fuzzy_threshold=78):
    """
    Search the Hindcon dataset by category name.

    This is separate from search_products() so product-name search
    behavior remains unchanged.

    The function supports:
        - exact category names
        - partial category names
        - spelling mistakes
        - multiple categories per product
        - multiple category rows for the same product

    Example:

        search_categories(df, "Waterproofing Compounds")

    returns every product belonging to that category, with its
    Product_Name, TDS_Link and MSDS_Link.

    If one product belongs to multiple categories, it is returned
    only once.
    """

    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])

    if not isinstance(query, str):
        return pd.DataFrame(columns=df.columns)

    query = query.strip()

    if not query or "Category" not in df.columns:
        return pd.DataFrame(columns=df.columns)

    matches = []

    for index, row in df.iterrows():
        categories = _split_categories(row.get("Category", ""))

        best_score = 0
        best_category = ""

        for category in categories:
            score = calculate_category_score(query, category)

            if score > best_score:
                best_score = score
                best_category = category

        # Use a slightly stricter threshold for very short searches.
        normalized_query = normalize_text(query)

        if len(normalized_query) <= 3:
            required_score = 94
        elif len(normalized_query) <= 5:
            required_score = 88
        else:
            required_score = fuzzy_threshold

        if best_score >= required_score:
            matches.append(
                {
                    "index": index,
                    "score": best_score,
                    "matched_category": best_category
                }
            )

    if not matches:
        return pd.DataFrame(columns=df.columns)

    matches.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    matched_indexes = [item["index"] for item in matches]
    result = df.loc[matched_indexes].copy()

    # Add internal category match score only temporarily.
    score_map = {
        item["index"]: item["score"]
        for item in matches
    }

    result["_category_match_score"] = result.index.map(score_map)
    result = result.sort_values(
        by="_category_match_score",
        ascending=False
    )

    result = result.drop(
        columns=["_category_match_score"],
        errors="ignore"
    )

    # Critical: one product = one result, even when the product has
    # multiple categories or multiple rows in the Excel file.
    result = _clean_category_results(result)

    return result


def is_category_search(df, query, fuzzy_threshold=78):
    """
    Return True when the query matches at least one category.

    This can be used by app.py to decide whether to run a category
    search before a normal product-name search.
    """

    results = search_categories(
        df,
        query,
        fuzzy_threshold=fuzzy_threshold
    )

    return not results.empty

