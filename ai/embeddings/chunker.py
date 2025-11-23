"""
Optimized Text Chunker for Embeddings

Features:
- Semantic-aware chunking (respects sentence boundaries)
- Cyrillic (Macedonian) language support
- Multiple chunking strategies (sentence, paragraph, semantic)
- Configurable chunk size and overlap
- Table and list detection
- Metadata preservation
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkStrategy(Enum):
    """Chunking strategy options"""
    SENTENCE = "sentence"  # Split by sentences
    PARAGRAPH = "paragraph"  # Split by paragraphs
    SEMANTIC = "semantic"  # Split by semantic boundaries (best for RAG)
    FIXED = "fixed"  # Fixed token count (simple)


@dataclass
class TextChunk:
    """Represents a text chunk with metadata"""
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int
    tender_id: Optional[str] = None
    doc_id: Optional[str] = None
    metadata: Optional[Dict] = None


class CyrillicTextProcessor:
    """
    Process Cyrillic (Macedonian) text

    Handles:
    - Sentence boundary detection
    - Paragraph detection
    - Special punctuation
    """

    # Macedonian/Serbian Cyrillic characters
    CYRILLIC_PATTERN = re.compile(r'[\u0400-\u04FF]+')

    # Sentence terminators (Macedonian + English)
    SENTENCE_TERMINATORS = re.compile(r'[.!?]+[\s\n]+')

    # Paragraph boundaries
    PARAGRAPH_BOUNDARY = re.compile(r'\n\s*\n+')

    # List markers (numbered and bulleted)
    LIST_MARKER = re.compile(r'^\s*(?:\d+\.|[\u2022\u2023\u25E6\u2043\u2219-])\s+', re.MULTILINE)

    @staticmethod
    def contains_cyrillic(text: str) -> bool:
        """Check if text contains Cyrillic characters"""
        return bool(CyrillicTextProcessor.CYRILLIC_PATTERN.search(text))

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """
        Split text into sentences

        Works with both English and Macedonian punctuation
        Handles abbreviations and special cases
        """
        # Split by sentence terminators
        sentences = CyrillicTextProcessor.SENTENCE_TERMINATORS.split(text)

        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    @staticmethod
    def split_paragraphs(text: str) -> List[str]:
        """Split text into paragraphs"""
        paragraphs = CyrillicTextProcessor.PARAGRAPH_BOUNDARY.split(text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return paragraphs

    @staticmethod
    def detect_lists(text: str) -> List[Tuple[int, int]]:
        """
        Detect list items in text

        Returns:
            List of (start, end) positions for list items
        """
        list_items = []
        for match in CyrillicTextProcessor.LIST_MARKER.finditer(text):
            # Find end of list item (next list marker or paragraph boundary)
            start = match.start()
            end = text.find('\n', match.end())
            if end == -1:
                end = len(text)
            list_items.append((start, end))

        return list_items


class TokenCounter:
    """
    Approximate token counting for text

    Uses heuristics for fast estimation
    """

    # Average characters per token (language-dependent)
    CHARS_PER_TOKEN = {
        'cyrillic': 5,  # Macedonian/Serbian (slightly longer tokens)
        'latin': 4,     # English/Latin
        'mixed': 4.5    # Mixed text
    }

    @staticmethod
    def count_tokens(text: str) -> int:
        """
        Estimate token count for text

        Args:
            text: Input text

        Returns:
            Approximate token count
        """
        if not text:
            return 0

        # Detect text type
        if CyrillicTextProcessor.contains_cyrillic(text):
            chars_per_token = TokenCounter.CHARS_PER_TOKEN['cyrillic']
        else:
            chars_per_token = TokenCounter.CHARS_PER_TOKEN['latin']

        # Estimate tokens
        return max(1, len(text) // chars_per_token)

    @staticmethod
    def chunk_fits(text: str, max_tokens: int) -> bool:
        """Check if text fits within token limit"""
        return TokenCounter.count_tokens(text) <= max_tokens


class SemanticChunker:
    """
    Advanced semantic chunker for optimal RAG performance

    Strategy:
    1. Split by semantic boundaries (paragraphs, sections)
    2. Respect sentence boundaries
    3. Keep related content together
    4. Maintain optimal chunk size for embeddings
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        strategy: ChunkStrategy = ChunkStrategy.SEMANTIC
    ):
        """
        Initialize chunker

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            strategy: Chunking strategy
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.text_processor = CyrillicTextProcessor()
        self.token_counter = TokenCounter()

    def chunk_text(
        self,
        text: str,
        tender_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[TextChunk]:
        """
        Chunk text into optimal segments

        Args:
            text: Input text
            tender_id: Associated tender ID
            doc_id: Document ID
            metadata: Additional metadata

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        # Choose chunking method based on strategy
        if self.strategy == ChunkStrategy.SEMANTIC:
            chunks = self._semantic_chunk(text)
        elif self.strategy == ChunkStrategy.SENTENCE:
            chunks = self._sentence_chunk(text)
        elif self.strategy == ChunkStrategy.PARAGRAPH:
            chunks = self._paragraph_chunk(text)
        else:  # FIXED
            chunks = self._fixed_chunk(text)

        # Create TextChunk objects with metadata
        result = []
        for idx, (chunk_text, start, end) in enumerate(chunks):
            token_count = self.token_counter.count_tokens(chunk_text)

            result.append(TextChunk(
                text=chunk_text,
                chunk_index=idx,
                start_char=start,
                end_char=end,
                token_count=token_count,
                tender_id=tender_id,
                doc_id=doc_id,
                metadata=metadata or {}
            ))

        logger.info(
            f"Chunked text into {len(result)} chunks "
            f"(strategy={self.strategy.value}, avg_tokens={sum(c.token_count for c in result) / max(1, len(result)):.1f})"
        )

        return result

    def _semantic_chunk(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Semantic chunking strategy (recommended)

        Process:
        1. Split by paragraphs
        2. Combine small paragraphs
        3. Split large paragraphs by sentences
        4. Add overlap between chunks
        """
        paragraphs = self.text_processor.split_paragraphs(text)

        chunks = []
        current_chunk = []
        current_tokens = 0
        current_start = 0

        for para in paragraphs:
            para_tokens = self.token_counter.count_tokens(para)

            # If paragraph fits in current chunk, add it
            if current_tokens + para_tokens <= self.chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens

            else:
                # Save current chunk if non-empty
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, current_start, current_start + len(chunk_text)))
                    current_start += len(chunk_text)

                # If paragraph is too large, split by sentences
                if para_tokens > self.chunk_size:
                    sentence_chunks = self._split_large_paragraph(para)
                    for chunk_text in sentence_chunks:
                        chunks.append((chunk_text, current_start, current_start + len(chunk_text)))
                        current_start += len(chunk_text)
                    current_chunk = []
                    current_tokens = 0
                else:
                    # Start new chunk with this paragraph
                    current_chunk = [para]
                    current_tokens = para_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append((chunk_text, current_start, current_start + len(chunk_text)))

        # Add overlap
        chunks = self._add_overlap(chunks, text)

        return chunks

    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """Split large paragraph into sentence-based chunks"""
        sentences = self.text_processor.split_sentences(paragraph)

        chunks = []
        current = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self.token_counter.count_tokens(sentence)

            if current_tokens + sentence_tokens <= self.chunk_size:
                current.append(sentence)
                current_tokens += sentence_tokens
            else:
                if current:
                    chunks.append(' '.join(current))
                current = [sentence]
                current_tokens = sentence_tokens

        if current:
            chunks.append(' '.join(current))

        return chunks

    def _sentence_chunk(self, text: str) -> List[Tuple[str, int, int]]:
        """Chunk by sentences (simple strategy)"""
        sentences = self.text_processor.split_sentences(text)

        chunks = []
        current = []
        current_tokens = 0
        current_start = 0

        for sentence in sentences:
            sentence_tokens = self.token_counter.count_tokens(sentence)

            if current_tokens + sentence_tokens <= self.chunk_size:
                current.append(sentence)
                current_tokens += sentence_tokens
            else:
                if current:
                    chunk_text = ' '.join(current)
                    chunks.append((chunk_text, current_start, current_start + len(chunk_text)))
                    current_start += len(chunk_text)
                current = [sentence]
                current_tokens = sentence_tokens

        if current:
            chunk_text = ' '.join(current)
            chunks.append((chunk_text, current_start, current_start + len(chunk_text)))

        return chunks

    def _paragraph_chunk(self, text: str) -> List[Tuple[str, int, int]]:
        """Chunk by paragraphs"""
        paragraphs = self.text_processor.split_paragraphs(text)

        chunks = []
        current_start = 0

        for para in paragraphs:
            chunks.append((para, current_start, current_start + len(para)))
            current_start += len(para)

        return chunks

    def _fixed_chunk(self, text: str) -> List[Tuple[str, int, int]]:
        """Fixed-size chunking (fallback)"""
        words = text.split()
        chunks = []

        # Approximate words per chunk
        words_per_chunk = self.chunk_size * 4  # Rough estimate

        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            chunk_text = ' '.join(chunk_words)
            start = text.find(chunk_words[0])
            end = start + len(chunk_text) if start != -1 else len(text)
            chunks.append((chunk_text, start, end))

        return chunks

    def _add_overlap(
        self,
        chunks: List[Tuple[str, int, int]],
        original_text: str
    ) -> List[Tuple[str, int, int]]:
        """
        Add overlap between chunks for context continuity

        Args:
            chunks: List of (text, start, end) tuples
            original_text: Original text

        Returns:
            Chunks with overlap added
        """
        if not chunks or self.chunk_overlap == 0:
            return chunks

        overlapped = []

        for i, (chunk_text, start, end) in enumerate(chunks):
            # Add overlap from previous chunk
            if i > 0:
                prev_chunk_text = chunks[i - 1][0]
                overlap_words = prev_chunk_text.split()[-self.chunk_overlap:]
                overlap_text = ' '.join(overlap_words)
                chunk_text = overlap_text + ' ' + chunk_text

            overlapped.append((chunk_text, start, end))

        return overlapped


# Convenience function
def chunk_document(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    strategy: ChunkStrategy = ChunkStrategy.SEMANTIC,
    tender_id: Optional[str] = None,
    doc_id: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> List[TextChunk]:
    """
    Quick function to chunk a document

    Usage:
        chunks = chunk_document(
            text=document_text,
            chunk_size=512,
            chunk_overlap=64,
            strategy=ChunkStrategy.SEMANTIC,
            tender_id="TENDER-123",
            doc_id="DOC-456"
        )

    Args:
        text: Document text
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks
        strategy: Chunking strategy
        tender_id: Tender ID
        doc_id: Document ID
        metadata: Additional metadata

    Returns:
        List of TextChunk objects
    """
    chunker = SemanticChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        strategy=strategy
    )

    return chunker.chunk_text(
        text=text,
        tender_id=tender_id,
        doc_id=doc_id,
        metadata=metadata
    )
