import re

# List marker pattern for bullet points and numbered lists
LIST_MARKER_PATTERN = re.compile(r"^(\s*[-*•–—]\s+|\s*\d+[\.\)]\s+|\s*[a-zA-Z][\.\)]\s+)")


def clean_text(text: str) -> str:
    """
    Clean and normalize extracted text from documents.
    
    - Removes extraction artifacts (null bytes, form feeds, replacement chars).
    - Normalizes line endings and non-breaking spaces.
    - Resolves soft hyphenations across line breaks.
    - Normalizes repeated horizontal whitespace.
    - Joins artificially wrapped lines within paragraphs while preserving list items.
    - Preserves meaningful paragraph boundaries (double newlines).
    - Trims leading/trailing whitespace without rewriting or summarizing content.
    """
    if not text:
        return ""

    # 1. Remove null bytes and unprintable/control characters (keep \n and \t temporarily)
    cleaned = text.replace("\x00", "").replace("\x0c", "").replace("\ufffd", "")

    # 2. Normalize carriage returns and non-breaking spaces
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u00a0", " ").replace("\u200b", "")

    # 3. Resolve hyphenation across line breaks: e.g. "docu-\nment" -> "document"
    cleaned = re.sub(r"([a-zA-Z]{2,})-\n([a-z]{2,})", r"\1\2", cleaned)

    # 4. Normalize multiple horizontal spaces and tabs on any line
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    # 5. Split into paragraph blocks separated by 2 or more newlines
    paragraphs = re.split(r"\n{2,}", cleaned)
    cleaned_paragraphs = []

    for para in paragraphs:
        lines = [line.strip() for line in para.split("\n") if line.strip()]
        if not lines:
            continue

        # Check if the paragraph consists of list items
        processed_lines = []
        current_item = []

        for line in lines:
            if LIST_MARKER_PATTERN.match(line):
                if current_item:
                    processed_lines.append(" ".join(current_item))
                    current_item = []
                current_item.append(line)
            else:
                if current_item:
                    # Append continuation of list item or regular line
                    current_item.append(line)
                else:
                    current_item.append(line)

        if current_item:
            processed_lines.append(" ".join(current_item))

        para_text = "\n".join(processed_lines)
        if para_text:
            cleaned_paragraphs.append(para_text)

    # 6. Recombine paragraphs with clean double newline
    result = "\n\n".join(cleaned_paragraphs).strip()
    return result
