import ast
import re
from typing import List, Optional


EMPTY_RESPONSE = "Sorry! No relevant content was found in the knowledge base!"

def clean_chat_completion_result(result: str) -> str:
    """
    Clean the raw LLM response to extract just the list part.
    """
    if not result or not isinstance(result, str):
        return ""

    # Remove leading/trailing whitespace
    cleaned = result.strip()

    # Remove markdown code blocks if present
    cleaned = re.sub(r'```(?:json|python|text)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```', '', cleaned)

    # Extract the list pattern [...]
    list_match = re.search(r'\[[\s\S]*?\]', cleaned)
    if list_match:
        return list_match.group(0)

    return cleaned


def parse_chat_completion_result(result: str) -> List[str]:
    """
    Parse the LLM response using ast.literal_eval for Python list format.
    Falls back to manual parsing if AST fails.
    """
    # Check for empty response pattern first
    if not result or EMPTY_RESPONSE in result:
        return []
    
    cleaned_result = _remove_id_references(result)
    cleaned_result = clean_chat_completion_result(cleaned_result)

    if not cleaned_result:
        return []

    # Remove RAGFlow ID references that break Python syntax

    # Try AST parsing first (most reliable for Python list format)
    try:
        parsed = ast.literal_eval(cleaned_result)
        if isinstance(parsed, list):
            # Convert all items to strings and filter empty ones
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError) as e:
        print(f"⚠️ AST parsing failed: {e}")
        print(f"🔍 Trying fallback parsing...")

        # Fallback to manual parsing
        return _parse_list_fallback(cleaned_result)

    return []


def _remove_id_references(text: str) -> str:
    """
    Remove RAGFlow ID references like [ID:1], [ID:2] etc. that break Python syntax.
    """
    # Remove patterns like [ID:1], [ID:2], [ID:123] etc.
    return re.sub(r'\s*\[ID:\d+\]', '', text)


def _parse_list_fallback(text: str) -> List[str]:
    """
    Fallback parsing when AST fails.
    """
    items = []

    # Remove brackets if present
    text = text.strip('[]')

    # Split by comma and clean each item
    parts = text.split('",')

    for part in parts:
        # Clean up quotes and whitespace
        clean_part = part.strip().strip('\'"').strip()
        if clean_part and len(clean_part) > 3:
            items.append(clean_part)

    return items

# not found in knowledge base 
