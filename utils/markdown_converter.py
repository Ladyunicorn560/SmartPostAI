"""
Utility to convert markdown content to LinkedIn-friendly plain text format.
LinkedIn doesn't support markdown, so we need to convert it to readable plain text.
"""

import re


def markdown_to_linkedin(text: str) -> str:
    """
    Convert markdown text to LinkedIn-compatible format.
    
    LinkedIn supports:
    - Line breaks
    - URLs (auto-linked)
    - Plain text
    
    LinkedIn does NOT support:
    - Markdown bold/italic syntax
    - Markdown links [text](url)
    - Markdown headers
    - Markdown lists
    
    We preserve markdown format but convert to LinkedIn-compatible:
    - Keep URLs as plain URLs (LinkedIn will auto-link)
    - Convert [text](url) to "text - url" format
    - Remove markdown syntax but keep content
    - Preserve line breaks
    
    Args:
        text: Markdown formatted text
        
    Returns:
        LinkedIn-compatible text (markdown removed, content preserved)
    """
    if not text:
        return ""
    
    # Convert markdown links [text](url) to "text - url" (LinkedIn will auto-link URL)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 - \2', text)
    
    # Remove markdown bold **text** -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # Remove markdown italic *text* -> text
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'\1', text)
    text = re.sub(r'_([^_\n]+?)_', r'\1', text)
    
    # Remove markdown headers (# Header -> Header)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    
    # Convert markdown lists to plain text with line breaks
    lines = text.split('\n')
    result_lines = []
    
    for line in lines:
        # Convert list items to plain text
        list_match = re.match(r'^[\s]*[-*]\s+(.+)$', line)
        if list_match:
            result_lines.append(list_match.group(1))
        else:
            result_lines.append(line)
    
    text = '\n'.join(result_lines)
    
    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Clean up multiple consecutive newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Clean up extra whitespace (but preserve line breaks)
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
    text = text.strip()
    
    return text

