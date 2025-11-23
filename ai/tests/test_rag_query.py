"""
Tests for RAG query pipeline

Tests context assembly, prompt building, and question answering
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from rag_query import (
    SearchResult,
    RAGAnswer,
    ContextAssembler,
    PromptBuilder,
    RAGQueryPipeline,
    ConversationManager
)


# Test Data

SAMPLE_SEARCH_RESULTS = [
    SearchResult(
        embed_id='uuid-1',
        chunk_text='Јавен повик за набавка на канцелариски материјали. Проценета вредност: 500.000 МКД.',
        chunk_index=0,
        tender_id='TENDER-001',
        doc_id='DOC-001',
        chunk_metadata={'type': 'tender_notice'},
        similarity=0.95
    ),
    SearchResult(
        embed_id='uuid-2',
        chunk_text='Референтен број: 2024-001-КАНЦ. Рок за доставување понуди: 30.11.2024.',
        chunk_index=1,
        tender_id='TENDER-001',
        doc_id='DOC-001',
        chunk_metadata={'type': 'tender_notice'},
        similarity=0.87
    ),
    SearchResult(
        embed_id='uuid-3',
        chunk_text='Нарачател: Општина Скопје. Адреса: бул. Илинден 82, Скопје.',
        chunk_index=2,
        tender_id='TENDER-001',
        doc_id='DOC-001',
        chunk_metadata={'type': 'tender_notice'},
        similarity=0.82
    )
]


class TestSearchResult:
    """Test SearchResult dataclass"""

    def test_creation(self):
        """Test creating SearchResult"""
        result = SearchResult(
            embed_id='test-id',
            chunk_text='Test text',
            chunk_index=0,
            tender_id='T-001',
            doc_id='D-001',
            chunk_metadata={'key': 'value'},
            similarity=0.95
        )

        assert result.embed_id == 'test-id'
        assert result.chunk_text == 'Test text'
        assert result.similarity == 0.95


class TestRAGAnswer:
    """Test RAGAnswer dataclass"""

    def test_creation(self):
        """Test creating RAGAnswer"""
        answer = RAGAnswer(
            question='Test question?',
            answer='Test answer',
            sources=SAMPLE_SEARCH_RESULTS,
            confidence='high',
            generated_at=datetime.utcnow(),
            model_used='gpt-4'
        )

        assert answer.question == 'Test question?'
        assert answer.answer == 'Test answer'
        assert len(answer.sources) == 3
        assert answer.confidence == 'high'


class TestContextAssembler:
    """Test ContextAssembler class"""

    def test_assemble_context_basic(self):
        """Test basic context assembly"""
        context, sources = ContextAssembler.assemble_context(
            SAMPLE_SEARCH_RESULTS,
            max_tokens=3000
        )

        assert len(sources) == 3
        assert '[Source 1]' in context
        assert '[Source 2]' in context
        assert '[Source 3]' in context
        assert 'TENDER-001' in context

    def test_assemble_context_empty(self):
        """Test assembling context from empty results"""
        context, sources = ContextAssembler.assemble_context([])

        assert context == ""
        assert sources == []

    def test_assemble_context_token_limit(self):
        """Test context respects token limit"""
        # Create many results
        many_results = [
            SearchResult(
                embed_id=f'uuid-{i}',
                chunk_text='A' * 1000,  # ~250 tokens
                chunk_index=i,
                tender_id='T-001',
                doc_id='D-001',
                chunk_metadata={},
                similarity=0.9 - (i * 0.01)
            )
            for i in range(20)
        ]

        context, sources = ContextAssembler.assemble_context(
            many_results,
            max_tokens=500  # Should fit ~2 chunks
        )

        # Should have limited number of sources
        assert len(sources) <= 3  # Approximate

    def test_assemble_context_deduplication(self):
        """Test that duplicate chunks are removed"""
        duplicate_results = [
            SearchResult(
                embed_id='uuid-1',
                chunk_text='Same text content here',
                chunk_index=0,
                tender_id='T-001',
                doc_id='D-001',
                chunk_metadata={},
                similarity=0.95
            ),
            SearchResult(
                embed_id='uuid-2',
                chunk_text='Same text content here',  # Duplicate
                chunk_index=1,
                tender_id='T-001',
                doc_id='D-002',
                chunk_metadata={},
                similarity=0.85
            ),
            SearchResult(
                embed_id='uuid-3',
                chunk_text='Different text content',
                chunk_index=2,
                tender_id='T-002',
                doc_id='D-003',
                chunk_metadata={},
                similarity=0.80
            )
        ]

        context, sources = ContextAssembler.assemble_context(duplicate_results)

        # Should only have 2 unique chunks
        assert len(sources) == 2

    def test_assemble_context_sorting(self):
        """Test results are sorted by similarity"""
        unsorted_results = [
            SearchResult(
                embed_id='uuid-1',
                chunk_text='Low similarity',
                chunk_index=0,
                tender_id='T-001',
                doc_id='D-001',
                chunk_metadata={},
                similarity=0.60
            ),
            SearchResult(
                embed_id='uuid-2',
                chunk_text='High similarity',
                chunk_index=1,
                tender_id='T-002',
                doc_id='D-002',
                chunk_metadata={},
                similarity=0.95
            ),
            SearchResult(
                embed_id='uuid-3',
                chunk_text='Medium similarity',
                chunk_index=2,
                tender_id='T-003',
                doc_id='D-003',
                chunk_metadata={},
                similarity=0.75
            )
        ]

        context, sources = ContextAssembler.assemble_context(unsorted_results)

        # First source should have highest similarity
        assert sources[0].similarity == 0.95
        assert sources[1].similarity == 0.75
        assert sources[2].similarity == 0.60

    def test_determine_confidence_high(self):
        """Test high confidence determination"""
        high_sim_sources = [
            SearchResult('id1', 'text', 0, 'T1', 'D1', {}, 0.90),
            SearchResult('id2', 'text', 1, 'T1', 'D1', {}, 0.85),
            SearchResult('id3', 'text', 2, 'T1', 'D1', {}, 0.88)
        ]

        confidence = ContextAssembler.determine_confidence(high_sim_sources)
        assert confidence == 'high'

    def test_determine_confidence_medium(self):
        """Test medium confidence determination"""
        medium_sim_sources = [
            SearchResult('id1', 'text', 0, 'T1', 'D1', {}, 0.70),
            SearchResult('id2', 'text', 1, 'T1', 'D1', {}, 0.65),
            SearchResult('id3', 'text', 2, 'T1', 'D1', {}, 0.68)
        ]

        confidence = ContextAssembler.determine_confidence(medium_sim_sources)
        assert confidence == 'medium'

    def test_determine_confidence_low(self):
        """Test low confidence determination"""
        low_sim_sources = [
            SearchResult('id1', 'text', 0, 'T1', 'D1', {}, 0.50),
            SearchResult('id2', 'text', 1, 'T1', 'D1', {}, 0.45),
            SearchResult('id3', 'text', 2, 'T1', 'D1', {}, 0.48)
        ]

        confidence = ContextAssembler.determine_confidence(low_sim_sources)
        assert confidence == 'low'

    def test_determine_confidence_empty(self):
        """Test confidence with empty sources"""
        confidence = ContextAssembler.determine_confidence([])
        assert confidence == 'low'


class TestPromptBuilder:
    """Test PromptBuilder class"""

    def test_system_prompt_exists(self):
        """Test system prompt is defined"""
        assert len(PromptBuilder.SYSTEM_PROMPT) > 0
        assert 'Macedonian' in PromptBuilder.SYSTEM_PROMPT
        assert 'procurement' in PromptBuilder.SYSTEM_PROMPT

    def test_build_query_prompt_basic(self):
        """Test basic prompt building"""
        messages = PromptBuilder.build_query_prompt(
            question="What is the budget?",
            context="Budget: 500.000 МКД"
        )

        assert len(messages) >= 2
        assert messages[0]['role'] == 'system'
        assert messages[-1]['role'] == 'user'
        assert 'What is the budget?' in messages[-1]['content']
        assert 'Budget: 500.000 МКД' in messages[-1]['content']

    def test_build_query_prompt_with_history(self):
        """Test prompt building with conversation history"""
        history = [
            {'question': 'Previous question?', 'answer': 'Previous answer.'},
            {'question': 'Another question?', 'answer': 'Another answer.'}
        ]

        messages = PromptBuilder.build_query_prompt(
            question="Current question?",
            context="Context text",
            conversation_history=history
        )

        # Should have system + history (2 msgs each) + current
        # = 1 + 4 + 1 = 6 messages
        assert len(messages) >= 6

        # Check history is included
        user_messages = [m['content'] for m in messages if m['role'] == 'user']
        assert any('Previous question?' in msg for msg in user_messages)

    def test_build_query_prompt_limits_history(self):
        """Test that only last 3 history turns are included"""
        history = [
            {'question': f'Q{i}?', 'answer': f'A{i}.'}
            for i in range(10)  # 10 turns
        ]

        messages = PromptBuilder.build_query_prompt(
            question="Current?",
            context="Context",
            conversation_history=history
        )

        # Should have system + last 3 history (6 msgs) + current = 8
        assert len(messages) == 8


class TestRAGQueryPipeline:
    """Test RAGQueryPipeline class"""

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    def test_initialization(self):
        """Test pipeline initialization"""
        pipeline = RAGQueryPipeline()

        assert pipeline.model == 'gpt-4'
        assert pipeline.top_k == 5
        assert pipeline.embedder is not None
        assert pipeline.vector_store is not None

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    @patch('openai.Embedding.create')
    @patch('openai.ChatCompletion.create')
    @pytest.mark.asyncio
    async def test_generate_answer(self, mock_chat, mock_embed):
        """Test answer generation"""
        # Mock embedding generation
        mock_embed.return_value = {
            'data': [{'embedding': [0.1] * 1536}]
        }

        # Mock chat completion
        mock_chat.return_value = {
            'choices': [{
                'message': {
                    'content': 'The budget is 500.000 МКД.'
                }
            }]
        }

        # Mock vector store
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                'embed_id': 'uuid-1',
                'chunk_text': 'Проценета вредност: 500.000 МКД',
                'chunk_index': 0,
                'tender_id': 'T-001',
                'doc_id': 'D-001',
                'chunk_metadata': {},
                'similarity': 0.95
            }
        ]

        pipeline = RAGQueryPipeline()
        pipeline.vector_store.conn = mock_conn

        answer = await pipeline.generate_answer("What is the budget?")

        assert answer.question == "What is the budget?"
        assert answer.answer == 'The budget is 500.000 МКД.'
        assert len(answer.sources) > 0
        assert answer.confidence in ['high', 'medium', 'low']
        assert answer.model_used == 'gpt-4'

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    @patch('openai.Embedding.create')
    @pytest.mark.asyncio
    async def test_generate_answer_no_results(self, mock_embed):
        """Test answer when no relevant documents found"""
        # Mock embedding generation
        mock_embed.return_value = {
            'data': [{'embedding': [0.1] * 1536}]
        }

        # Mock vector store with no results
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        pipeline = RAGQueryPipeline()
        pipeline.vector_store.conn = mock_conn

        answer = await pipeline.generate_answer("What is XYZ?")

        assert answer.confidence == 'low'
        assert len(answer.sources) == 0
        assert "couldn't find" in answer.answer.lower()

    @patch.dict('os.environ', {
        'DATABASE_URL': 'postgresql://localhost/test',
        'OPENAI_API_KEY': 'test-key'
    })
    @patch('openai.Embedding.create')
    @patch('openai.ChatCompletion.create')
    @pytest.mark.asyncio
    async def test_generate_answer_with_tender_filter(self, mock_chat, mock_embed):
        """Test answer generation filtered by tender_id"""
        # Mock embedding
        mock_embed.return_value = {
            'data': [{'embedding': [0.1] * 1536}]
        }

        # Mock chat
        mock_chat.return_value = {
            'choices': [{'message': {'content': 'Answer'}}]
        }

        # Mock vector store
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                'embed_id': 'uuid-1',
                'chunk_text': 'Text',
                'chunk_index': 0,
                'tender_id': 'T-001',
                'doc_id': 'D-001',
                'chunk_metadata': {},
                'similarity': 0.95
            }
        ]

        pipeline = RAGQueryPipeline()
        pipeline.vector_store.conn = mock_conn

        answer = await pipeline.generate_answer(
            "Question?",
            tender_id='T-001'
        )

        # Verify tender_id was passed to similarity_search
        call_args = mock_conn.fetch.call_args
        assert 'T-001' in call_args[0]


class TestConversationManager:
    """Test ConversationManager class"""

    @patch.dict('os.environ', {'DATABASE_URL': 'postgresql://localhost/test'})
    def test_initialization(self):
        """Test conversation manager initialization"""
        manager = ConversationManager()
        assert manager.database_url == 'postgresql://localhost/test'
        assert manager.conn is None

    @pytest.mark.asyncio
    async def test_save_interaction(self):
        """Test saving user interaction"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {'conversation_id': 'conv-123'}

        manager = ConversationManager('postgresql://localhost/test')
        manager.conn = mock_conn

        conv_id = await manager.save_interaction(
            user_id='user-123',
            question='Test question?',
            answer='Test answer',
            sources=SAMPLE_SEARCH_RESULTS,
            confidence='high',
            model_used='gpt-4'
        )

        assert conv_id == 'conv-123'
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_history(self):
        """Test retrieving user conversation history"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                'question': 'Q1?',
                'answer': 'A1',
                'created_at': datetime.utcnow()
            },
            {
                'question': 'Q2?',
                'answer': 'A2',
                'created_at': datetime.utcnow()
            }
        ]

        manager = ConversationManager('postgresql://localhost/test')
        manager.conn = mock_conn

        history = await manager.get_user_history('user-123', limit=10)

        assert len(history) == 2
        assert history[0]['question'] == 'Q2?'  # Reversed order
        assert history[1]['question'] == 'Q1?'


# Integration-style tests

@pytest.mark.integration
class TestRAGIntegration:
    """
    Integration tests for RAG pipeline

    NOTE: These tests require:
    - PostgreSQL with pgvector
    - Valid DATABASE_URL
    - Valid OPENAI_API_KEY
    - embeddings table with data
    """

    @pytest.mark.asyncio
    async def test_full_rag_pipeline_integration(self):
        """Test complete RAG pipeline end-to-end"""
        pytest.skip("Requires database and API key")

    @pytest.mark.asyncio
    async def test_macedonian_question_answering(self):
        """Test answering questions in Macedonian"""
        pytest.skip("Requires database and API key")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
