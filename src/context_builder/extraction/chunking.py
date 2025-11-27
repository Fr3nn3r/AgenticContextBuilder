"""
Markdown chunking with dynamic symbol filtering for token-constrained LLM processing.

Implements "Header-Aware Greedy Builder" algorithm that:
- Splits markdown at header boundaries
- Treats lists as atomic blocks
- Dynamically filters symbols per chunk
- Maximizes text content within token budget
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set, Optional

import tiktoken

from context_builder.utils.symbol_table_renderer import render_symbol_context

logger = logging.getLogger(__name__)

# Constants
MAX_TOKENS = 4000  # Reduced chunk size for more granular processing
HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
LIST_ITEM_PATTERN = re.compile(r"^[\s]*[-*+]|\d+\.")


@dataclass
class Block:
    """
    Atomic markdown block that cannot be split.

    Attributes:
        content: Raw text content
        block_type: "header" | "list" | "paragraph"
        parent_headers: Hierarchical list of parent headers
        line_start: Starting line number (for debugging)
    """

    content: str
    block_type: str
    parent_headers: List[str]
    line_start: int


def get_token_encoder(model_name: str):
    """
    Get tiktoken encoder for model with fallback.

    Args:
        model_name: OpenAI model name (e.g., "gpt-4o")

    Returns:
        tiktoken.Encoding instance
    """
    try:
        encoder = tiktoken.encoding_for_model(model_name)
        logger.debug(f"Using encoder: {encoder.name} for model: {model_name}")
        return encoder
    except KeyError:
        # Fallback for very new models
        logger.warning(f"Model {model_name} not in tiktoken, using o200k_base fallback")
        return tiktoken.get_encoding("o200k_base")


def count_tokens(text: str, encoder) -> int:
    """
    Count tokens in text using tiktoken encoder.

    Args:
        text: Text to count
        encoder: tiktoken encoder instance

    Returns:
        Number of tokens
    """
    return len(encoder.encode(text))


def parse_blocks(markdown_lines: List[str]) -> List[Block]:
    """
    Parse markdown into atomic blocks with header hierarchy.

    Blocks:
    - Header: Lines starting with #
    - List: Consecutive bullet/numbered items (atomic, cannot split)
    - Paragraph: Text between headers/lists

    Args:
        markdown_lines: List of markdown lines

    Returns:
        List of Block objects
    """
    blocks = []
    current_headers = []  # Stack of parent headers
    current_paragraph = []
    current_list = []
    line_num = 0

    for i, line in enumerate(markdown_lines):
        # Check if header
        header_match = HEADER_PATTERN.match(line)
        if header_match:
            # Flush any accumulated content
            if current_list:
                blocks.append(
                    Block(
                        content="\n".join(current_list),
                        block_type="list",
                        parent_headers=current_headers.copy(),
                        line_start=line_num,
                    )
                )
                current_list = []

            if current_paragraph:
                blocks.append(
                    Block(
                        content="\n".join(current_paragraph),
                        block_type="paragraph",
                        parent_headers=current_headers.copy(),
                        line_start=line_num,
                    )
                )
                current_paragraph = []

            # Update header stack
            level = len(header_match.group(1))  # Count #'s
            header_text = header_match.group(2).strip()

            # Pop headers at same or deeper level
            current_headers = [h for h in current_headers if h[0] < level]
            current_headers.append((level, header_text))

            # Add header as block
            blocks.append(
                Block(
                    content=line,
                    block_type="header",
                    parent_headers=current_headers.copy(),
                    line_start=i,
                )
            )
            line_num = i
            continue

        # Check if list item
        if LIST_ITEM_PATTERN.match(line):
            # Flush paragraph if exists
            if current_paragraph:
                blocks.append(
                    Block(
                        content="\n".join(current_paragraph),
                        block_type="paragraph",
                        parent_headers=current_headers.copy(),
                        line_start=line_num,
                    )
                )
                current_paragraph = []
                line_num = i

            # Accumulate list items
            current_list.append(line)
            continue

        # Empty line
        if not line.strip():
            # End list if active
            if current_list:
                blocks.append(
                    Block(
                        content="\n".join(current_list),
                        block_type="list",
                        parent_headers=current_headers.copy(),
                        line_start=line_num,
                    )
                )
                current_list = []
                line_num = i
            continue

        # Regular paragraph line
        if current_list:
            # List ended, flush it
            blocks.append(
                Block(
                    content="\n".join(current_list),
                    block_type="list",
                    parent_headers=current_headers.copy(),
                    line_start=line_num,
                )
            )
            current_list = []
            line_num = i

        current_paragraph.append(line)

    # Flush remaining content
    if current_list:
        blocks.append(
            Block(
                content="\n".join(current_list),
                block_type="list",
                parent_headers=current_headers.copy(),
                line_start=line_num,
            )
        )

    if current_paragraph:
        blocks.append(
            Block(
                content="\n".join(current_paragraph),
                block_type="paragraph",
                parent_headers=current_headers.copy(),
                line_start=line_num,
            )
        )

    return blocks


def build_symbol_trigger_map(symbol_table: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build unified symbol lookup map with regex patterns.

    Args:
        symbol_table: Dict with 'defined_terms' and 'explicit_variables' keys

    Returns:
        Dict mapping lowercase term/name to symbol data
    """
    trigger_map = {}

    # Add defined terms
    for item in symbol_table.get("defined_terms", []):
        key = item["term"].lower()
        trigger_map[key] = {
            "type": "term",
            "data": item,
            "pattern": re.compile(
                r"\b" + re.escape(item["term"]) + r"(?:s|es)?\b", re.IGNORECASE
            ),
        }

    # Add explicit variables
    for item in symbol_table.get("explicit_variables", []):
        key = item["name"].lower()
        trigger_map[key] = {
            "type": "variable",
            "data": item,
            "pattern": re.compile(
                r"\b" + re.escape(item["name"]) + r"(?:s|es)?\b", re.IGNORECASE
            ),
        }

    return trigger_map


def find_mentioned_symbols(
    text: str, trigger_map: Dict[str, Dict[str, Any]]
) -> Set[str]:
    """
    Find which symbols are mentioned in text using regex matching.

    Args:
        text: Text to scan
        trigger_map: Symbol lookup map with compiled regex patterns

    Returns:
        Set of lowercase symbol keys found in text
    """
    mentioned = set()

    for key, symbol_info in trigger_map.items():
        if symbol_info["pattern"].search(text):
            mentioned.add(key)

    return mentioned


def render_filtered_symbols(
    symbol_keys: Set[str], trigger_map: Dict[str, Dict[str, Any]]
) -> str:
    """
    Render markdown for filtered subset of symbols.

    Args:
        symbol_keys: Set of symbol keys to include
        trigger_map: Full symbol lookup map

    Returns:
        Markdown-formatted symbol table
    """
    # Build filtered symbol table
    filtered = {"defined_terms": [], "explicit_variables": []}

    for key in symbol_keys:
        symbol_info = trigger_map[key]
        if symbol_info["type"] == "term":
            filtered["defined_terms"].append(symbol_info["data"])
        elif symbol_info["type"] == "variable":
            filtered["explicit_variables"].append(symbol_info["data"])

    # Use existing renderer
    return render_symbol_context(filtered)


def chunk_markdown_with_symbols(
    markdown_path: str,
    symbol_table_json: Dict[str, Any],
    model_name: str,
    system_prompt_text: str,
    max_tokens: int = MAX_TOKENS,
) -> List[Tuple[str, str, int]]:
    """
    Chunk markdown with dynamic symbol filtering using greedy builder algorithm.

    Algorithm:
    1. Count system prompt tokens (fixed overhead)
    2. Parse markdown into atomic blocks
    3. Build symbol trigger map
    4. Greedily add blocks while budget allows:
       - Calculate new symbols introduced by block
       - Check if current + block + symbols < max_tokens
       - If fits: add, update active symbols
       - If overflow: yield chunk, reset

    Args:
        markdown_path: Path to markdown file
        symbol_table_json: Full symbol table dict
        model_name: OpenAI model name for token encoding
        system_prompt_text: System prompt text for token counting
        max_tokens: Maximum tokens per chunk (default: 8000)

    Returns:
        List of (chunk_text, filtered_symbol_md, chunk_tokens, symbol_keys) tuples
        where symbol_keys is a set of lowercase symbol keys mentioned in chunk
    """
    # Get encoder
    encoder = get_token_encoder(model_name)

    # Count system prompt overhead
    system_prompt_tokens = count_tokens(system_prompt_text, encoder)
    logger.info(f"System prompt overhead: {system_prompt_tokens} tokens")

    # Read and parse markdown
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_lines = f.readlines()

    blocks = parse_blocks(markdown_lines)
    logger.info(f"Parsed {len(blocks)} blocks from markdown")

    # Build symbol trigger map
    trigger_map = build_symbol_trigger_map(symbol_table_json["extracted_data"])
    logger.info(f"Built trigger map with {len(trigger_map)} symbols")

    # Greedy chunking loop
    chunks = []
    current_blocks = []
    current_symbols = set()

    for block in blocks:
        # Find new symbols in this block
        block_symbols = find_mentioned_symbols(block.content, trigger_map)
        potential_symbols = current_symbols.union(block_symbols)

        # Build potential chunk text with header context preservation
        potential_text_blocks = current_blocks + [block]
        chunk_content_parts = []
        first_block = potential_text_blocks[0]

        # Prepend parent header hierarchy if chunk starts with non-header block
        if first_block.block_type != "header" and first_block.parent_headers:
            header_context = "\n".join(
                f"{'#' * level} {text}" for level, text in first_block.parent_headers
            )
            chunk_content_parts.append(header_context)

        chunk_content_parts.extend(b.content for b in potential_text_blocks)
        potential_text = "\n\n".join(chunk_content_parts)

        # Render symbols
        potential_symbol_md = render_filtered_symbols(potential_symbols, trigger_map)

        # Calculate total cost
        text_tokens = count_tokens(potential_text, encoder)
        symbol_tokens = count_tokens(potential_symbol_md, encoder)
        total_tokens = system_prompt_tokens + text_tokens + symbol_tokens

        # Decision
        if total_tokens <= max_tokens:
            # Fits! Add it
            current_blocks.append(block)
            current_symbols = potential_symbols
        else:
            # Overflow! Check if we have accumulated content
            if current_blocks:
                # Ship what we have with header context preservation
                chunk_content_parts = []
                first_block = current_blocks[0]

                # Prepend parent header hierarchy if chunk starts with non-header block
                if first_block.block_type != "header" and first_block.parent_headers:
                    header_context = "\n".join(
                        f"{'#' * level} {text}"
                        for level, text in first_block.parent_headers
                    )
                    chunk_content_parts.append(header_context)

                chunk_content_parts.extend(b.content for b in current_blocks)
                chunk_text = "\n\n".join(chunk_content_parts)
                chunk_symbol_md = render_filtered_symbols(current_symbols, trigger_map)
                chunk_tokens = (
                    system_prompt_tokens
                    + count_tokens(chunk_text, encoder)
                    + count_tokens(chunk_symbol_md, encoder)
                )
                chunks.append((chunk_text, chunk_symbol_md, chunk_tokens, current_symbols))

                # Reset with rejected block
                current_blocks = [block]
                current_symbols = block_symbols
            else:
                # Oversized single block - process alone with warning
                block_tokens = count_tokens(block.content, encoder)
                block_symbol_md = render_filtered_symbols(block_symbols, trigger_map)
                total_block_tokens = (
                    system_prompt_tokens
                    + block_tokens
                    + count_tokens(block_symbol_md, encoder)
                )

                logger.warning(
                    f"Block at line {block.line_start} exceeds max tokens "
                    f"({total_block_tokens} > {max_tokens}). Processing as oversized chunk."
                )
                chunks.append((block.content, block_symbol_md, total_block_tokens, block_symbols))

                # Continue with empty state
                current_blocks = []
                current_symbols = set()

    # Flush remaining content with header context preservation
    if current_blocks:
        chunk_content_parts = []
        first_block = current_blocks[0]

        # Prepend parent header hierarchy if chunk starts with non-header block
        if first_block.block_type != "header" and first_block.parent_headers:
            header_context = "\n".join(
                f"{'#' * level} {text}" for level, text in first_block.parent_headers
            )
            chunk_content_parts.append(header_context)

        chunk_content_parts.extend(b.content for b in current_blocks)
        chunk_text = "\n\n".join(chunk_content_parts)
        chunk_symbol_md = render_filtered_symbols(current_symbols, trigger_map)
        chunk_tokens = (
            system_prompt_tokens
            + count_tokens(chunk_text, encoder)
            + count_tokens(chunk_symbol_md, encoder)
        )
        chunks.append((chunk_text, chunk_symbol_md, chunk_tokens, current_symbols))

    logger.info(f"Created {len(chunks)} chunks")
    return chunks


def save_chunks(
    chunks: List[Tuple[str, str, int, Set[str]]], base_path: Path
) -> List[Tuple[Path, Path]]:
    """
    Save chunks with zero-padded numbering.

    Creates:
    - output_chunks/{base}_chunk_001.md (text chunk)
    - output_chunks/{base}_chunk_001_symbol.md (filtered symbols)

    Args:
        chunks: List of (chunk_text, symbol_md, tokens) tuples
        base_path: Base path for output files

    Returns:
        List of (text_path, symbol_path) tuples
    """
    # Create chunks directory as 'output_chunks' subfolder
    chunks_dir = base_path.parent / "output_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunk_files = []
    num_digits = len(str(len(chunks)))

    for i, (chunk_text, symbol_md, tokens, symbol_keys) in enumerate(chunks, 1):
        # Zero-padded numbering
        chunk_num = str(i).zfill(num_digits)

        # Save text chunk
        text_path = chunks_dir / f"{base_path.name}_chunk_{chunk_num}.md"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(chunk_text)

        # Save symbol chunk
        symbol_path = chunks_dir / f"{base_path.name}_chunk_{chunk_num}_symbol.md"
        with open(symbol_path, "w", encoding="utf-8") as f:
            f.write(symbol_md)

        logger.info(
            f"Saved chunk {i}/{len(chunks)}: {tokens} tokens → {text_path.name}"
        )
        chunk_files.append((text_path, symbol_path))

    return chunk_files
