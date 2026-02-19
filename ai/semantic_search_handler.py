# Semantic Search Tool Handler for RAG Query
# This code should be inserted into rag_query.py after the search_bid_documents handler

SEMANTIC_SEARCH_HANDLER = """
    elif tool_name == "semantic_search_documents":
        # Vector similarity search using pgvector and Gemini embeddings
        query_text = tool_args.get("query", "")
        if not query_text:
            return "Не е даден текст за пребарување."

        limit = tool_args.get("limit", 5)
        min_similarity = tool_args.get("min_similarity", 0.5)

        # Validate parameters
        if limit > 20:
            limit = 20
        if min_similarity < 0 or min_similarity > 1:
            min_similarity = 0.5

        try:
            # 1. Generate query embedding using Gemini
            logger.info(f"Generating embedding for query: {query_text[:100]}...")
            embedder = EmbeddingGenerator(api_key=os.getenv('GEMINI_API_KEY'))
            query_vector = await embedder.generate_embedding(query_text)

            # 2. Perform vector similarity search using pgvector
            # Use cosine distance operator <=> (1 - cosine similarity)
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'

            # Search embeddings table with similarity threshold
            search_query = \"\"\"
                SELECT
                    e.embed_id,
                    e.chunk_text,
                    e.chunk_index,
                    e.tender_id,
                    e.doc_id,
                    e.metadata,
                    1 - (e.embedding <=> $1::vector) as similarity,
                    t.title as tender_title,
                    t.procuring_entity,
                    t.winner,
                    t.publication_date,
                    t.actual_value_mkd,
                    d.file_name,
                    d.doc_category
                FROM embeddings e
                LEFT JOIN tenders t ON e.tender_id = t.tender_id
                LEFT JOIN documents d ON e.doc_id = d.doc_id
                WHERE 1 - (e.embedding <=> $1::vector) >= $2
                ORDER BY e.embedding <=> $1::vector
                LIMIT $3
            \"\"\"

            rows = await conn.fetch(search_query, vector_str, min_similarity, limit)

            if not rows:
                return f"Не најдов семантички слични документи за: {query_text}\\n(Можеби пробајте со помал min_similarity или користете keyword search)"

            # 3. Format results with context
            result_parts = [
                f"🔍 Семантичко пребарување: {query_text}",
                f"Најдов {len(rows)} релевантни документи (сличност >= {min_similarity:.0%}):\\n"
            ]

            for i, row in enumerate(rows, 1):
                similarity_pct = row['similarity'] * 100
                chunk_text = row['chunk_text'][:1500] if row['chunk_text'] else "Нема содржина"

                result_parts.append(f"\\n{'='*60}")
                result_parts.append(f"Резултат #{i} (Сличност: {similarity_pct:.1f}%)")
                result_parts.append(f"{'='*60}")

                # Tender info (if available)
                if row['tender_title']:
                    result_parts.append(f"**Тендер:** {row['tender_title']}")
                if row['procuring_entity']:
                    result_parts.append(f"**Набавувач:** {row['procuring_entity']}")
                if row['winner']:
                    result_parts.append(f"**Победник:** {row['winner']}")
                if row['publication_date']:
                    result_parts.append(f"**Датум:** {row['publication_date']}")
                if row['actual_value_mkd']:
                    result_parts.append(f"**Вредност:** {row['actual_value_mkd']:,.0f} МКД")

                # Document info
                if row['file_name']:
                    result_parts.append(f"**Документ:** {row['file_name']} ({row['doc_category'] or 'N/A'})")

                # Metadata
                if row['metadata']:
                    metadata = row['metadata']
                    if isinstance(metadata, str):
                        import json
                        try:
                            metadata = json.loads(metadata)
                        except:
                            pass
                    if isinstance(metadata, dict) and metadata:
                        meta_str = ", ".join(f"{k}: {v}" for k, v in metadata.items() if v)
                        if meta_str:
                            result_parts.append(f"**Метаподатоци:** {meta_str}")

                # Chunk content
                result_parts.append(f"\\n**Содржина:**")
                result_parts.append(chunk_text)

            # Summary statistics
            avg_similarity = sum(r['similarity'] for r in rows) / len(rows)
            result_parts.append(f"\\n{'='*60}")
            result_parts.append(f"📊 Просечна сличност: {avg_similarity*100:.1f}%")
            result_parts.append(f"💡 Совет: За подобри резултати, користи специфични термини и опиши што бараш.")

            return "\\n".join(result_parts)

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return f"Грешка при семантичко пребарување: {str(e)}\\nПробајте со keyword search (search_bid_documents) како алтернатива."
"""

# Instructions for insertion:
# 1. Find line: elif tool_name == "web_search_procurement":
# 2. Insert the SEMANTIC_SEARCH_HANDLER code BEFORE that line
# 3. Make sure indentation matches the surrounding elif blocks
