"""
Long Document RAG Test Suite
Tests chunking + qwen retrieval + mistral final answer pipeline.
Evaluates coherence, accuracy, and citation quality.
"""

import asyncio
import time
import json
from pathlib import Path
import sys
import re

sys.path.insert(0, str(Path(__file__).parent))

from providers import OllamaAdapter
import os


# Sample long document for RAG testing
SAMPLE_DOCUMENT = """
# Azure Cosmos DB for NoSQL: Complete Guide

## Introduction
Azure Cosmos DB is Microsoft's globally distributed, multi-model database service. It offers turnkey global distribution across any number of Azure regions with transparent multi-region writes. The service provides guaranteed low latency, high availability, and elastic scalability.

## Key Features

### Global Distribution
Cosmos DB allows you to distribute your data globally across multiple Azure regions. You can add or remove regions at any time without application downtime. The service automatically replicates your data to all configured regions.

### Multi-Model Support
Cosmos DB supports multiple data models:
- Document (NoSQL)
- Key-value
- Graph (Gremlin)
- Column-family (Cassandra)
- Table

### Performance Guarantees
The service provides comprehensive SLAs covering:
- 99.999% availability for multi-region accounts
- Single-digit millisecond latency at P99 for reads and writes
- Guaranteed throughput and consistency

### Consistency Models
Cosmos DB offers 5 consistency levels:
1. Strong - Linearizability guarantee
2. Bounded Staleness - Configurable lag window
3. Session - Read-your-writes guarantee within a session
4. Consistent Prefix - Reads never see out-of-order writes
5. Eventual - Highest availability, lowest latency

## Pricing Model

### Request Units (RUs)
Cosmos DB uses Request Units as the currency for throughput. One RU represents the resources needed to read a 1KB document. Write operations cost more RUs than reads.

### Billing Options
- Provisioned throughput: Reserve RU/s capacity
- Serverless: Pay per request
- Autoscale: Automatically scale RU/s based on demand

### Cost Optimization
To optimize costs:
- Use appropriate consistency levels
- Optimize query patterns
- Leverage TTL for automatic data deletion
- Use composite indexes wisely
- Consider serverless for unpredictable workloads

## Partitioning Strategy

### Logical Partitions
Each item belongs to a logical partition determined by the partition key. Logical partitions are limited to 20GB.

### Physical Partitions
Azure automatically manages physical partitions. Data is distributed across physical partitions for scalability.

### Choosing a Partition Key
Select a partition key that:
- Has high cardinality (many distinct values)
- Distributes requests evenly
- Aligns with your query patterns
- Avoids hot partitions

### Hierarchical Partition Keys
New feature allowing up to 3 partition key paths for better data distribution and query flexibility.

## Best Practices

### Data Modeling
- Denormalize data where possible
- Embed related data for atomic operations
- Use reference IDs for large or frequently updated data
- Keep item sizes under 2MB

### Indexing
- Cosmos DB indexes all properties by default
- Customize indexing policy to exclude unused properties
- Use composite indexes for ORDER BY with multiple properties
- Leverage spatial and vector indexes when needed

### Query Optimization
- Avoid cross-partition queries when possible
- Use continuation tokens for pagination
- Leverage query metrics to identify bottlenecks
- Add filters early in the query pipeline

### Security
- Enable firewall rules
- Use private endpoints for VNet integration
- Implement RBAC with Azure AD
- Enable customer-managed keys for encryption
- Audit access with diagnostic logs

## Monitoring and Troubleshooting

### Metrics to Monitor
- Request rate and latency
- Throttled requests (429 errors)
- Storage consumption
- RU consumption patterns
- Cross-region replication lag

### Common Issues
1. Hot partitions - caused by poor partition key choice
2. Rate limiting - insufficient RU provisioning
3. High latency - suboptimal query patterns
4. High costs - over-provisioning or inefficient queries

### Diagnostic Tools
- Azure Portal metrics
- Log Analytics integration
- Cosmos DB Profiler
- Query statistics and metrics

## Integration Patterns

### Change Feed
Monitor and react to data changes in real-time. Use cases:
- Event-driven architectures
- Real-time analytics
- Data synchronization across systems
- Audit logging

### Azure Functions Integration
Trigger functions based on Cosmos DB events:
- Automatic document processing
- Real-time data pipelines
- Serverless workflows

### Synapse Link
Analyze operational data without affecting transactional workload:
- Near real-time analytics
- No ETL required
- Cost-effective analytical queries

## Conclusion
Azure Cosmos DB is a powerful globally distributed database service suitable for applications requiring low latency, high availability, and elastic scalability. Proper data modeling, partitioning strategy, and cost optimization are key to success.
"""


def chunk_document(text: str, chunk_size: int = 500) -> list:
    """Split document into chunks by paragraphs."""
    # Split by double newlines (paragraphs)
    paragraphs = re.split(r"\n\n+", text.strip())

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def retrieve_relevant_chunks(
    query: str, chunks: list, model_id: str = "qwen2.5:3b", top_k: int = 3
):
    """Use qwen2.5:3b to identify most relevant chunks."""
    ollama_base_url = os.getenv("LOCAL_LLM_PROXY_URL", "http://45.61.60.3:8002")
    ollama_api_key = os.getenv("LOCAL_LLM_API_KEY", "your-secure-api-key-here")
    adapter = OllamaAdapter(ollama_api_key, ollama_base_url)

    # Score each chunk
    scores = []
    print(f"\nScoring {len(chunks)} chunks with {model_id}...")

    for i, chunk in enumerate(chunks):
        prompt = f"""Rate the relevance of this text chunk to the query on a scale of 0-10.
Query: {query}

Text chunk:
{chunk[:300]}...

Respond with ONLY a number 0-10."""

        try:
            response = await adapter.chat(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
            )

            # Extract number from response
            score_match = re.search(r"\d+", response)
            score = int(score_match.group()) if score_match else 0
            scores.append((i, score, chunk))
            print(f"  Chunk {i + 1}: score={score}")

        except Exception as e:
            print(f"  Chunk {i + 1}: error - {e}")
            scores.append((i, 0, chunk))

    # Sort by score and return top_k
    scores.sort(key=lambda x: x[1], reverse=True)
    top_chunks = [chunk for _, _, chunk in scores[:top_k]]

    print(
        f"\nSelected top {top_k} chunks (scores: {[s for _, s, _ in scores[:top_k]]})"
    )

    return top_chunks


async def generate_answer(
    query: str, context_chunks: list, model_id: str = "mistral:7b"
):
    """Use mistral:7b to generate final answer from retrieved context."""
    ollama_base_url = os.getenv("LOCAL_LLM_PROXY_URL", "http://45.61.60.3:8002")
    ollama_api_key = os.getenv("LOCAL_LLM_API_KEY", "your-secure-api-key-here")
    adapter = OllamaAdapter(ollama_api_key, ollama_base_url)

    # Combine chunks into context
    context = "\n\n".join(
        [f"[Chunk {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)]
    )

    prompt = f"""Based on the provided context, answer the following question. If the answer is not in the context, say so explicitly. Cite which chunks you used.

Context:
{context}

Question: {query}

Answer:"""

    print(f"\nGenerating answer with {model_id}...")
    start_time = time.time()

    try:
        response = await adapter.chat(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=512,
        )

        end_time = time.time()
        latency = (end_time - start_time) * 1000

        return {
            "success": True,
            "answer": response,
            "latency_ms": round(latency, 2),
            "tokens": len(response.split()),
        }

    except Exception as e:
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        return {"success": False, "error": str(e), "latency_ms": round(latency, 2)}


def evaluate_answer_quality(answer: str, query: str):
    """Evaluate answer quality heuristically."""
    answer_lower = answer.lower()

    # Check for citation
    has_citation = bool(re.search(r"chunk \d+|according to|based on", answer_lower))

    # Check for refusal
    has_refusal = any(
        phrase in answer_lower
        for phrase in [
            "not in the context",
            "not provided",
            "don't have information",
            "cannot find",
            "not mentioned",
        ]
    )

    # Check coherence (basic metrics)
    sentences = re.split(r"[.!?]+", answer)
    avg_sentence_length = len(answer.split()) / max(len(sentences), 1)

    # Length check
    is_adequate_length = 20 < len(answer.split()) < 500

    # Score
    score = 0
    if has_citation:
        score += 30  # Good practice to cite sources
    if not has_refusal:
        score += 20  # Answered the question
    if 10 < avg_sentence_length < 30:
        score += 25  # Good sentence structure
    if is_adequate_length:
        score += 25  # Adequate detail

    quality = "GOOD" if score >= 70 else "FAIR" if score >= 50 else "POOR"

    return {
        "quality": quality,
        "score": score,
        "has_citation": has_citation,
        "has_refusal": has_refusal,
        "avg_sentence_length": round(avg_sentence_length, 1),
        "word_count": len(answer.split()),
    }


async def test_rag_pipeline(query: str, document: str):
    """Test complete RAG pipeline."""
    print(f"\n{'=' * 80}")
    print(f"RAG Pipeline Test")
    print(f"{'=' * 80}")
    print(f"\nQuery: {query}")

    # Step 1: Chunk document
    print(f"\n--- Step 1: Document Chunking ---")
    chunks = chunk_document(document, chunk_size=500)
    print(f"Document split into {len(chunks)} chunks")
    print(f"Average chunk size: {sum(len(c) for c in chunks) / len(chunks):.0f} chars")

    # Step 2: Retrieve relevant chunks with qwen2.5:3b
    print(f"\n--- Step 2: Retrieval (qwen2.5:3b) ---")
    start_retrieval = time.time()
    relevant_chunks = await retrieve_relevant_chunks(
        query, chunks, model_id="qwen2.5:3b", top_k=3
    )
    retrieval_time = (time.time() - start_retrieval) * 1000
    print(f"Retrieval completed in {retrieval_time:.0f}ms")

    # Step 3: Generate answer with mistral:7b
    print(f"\n--- Step 3: Answer Generation (mistral:7b) ---")
    result = await generate_answer(query, relevant_chunks, model_id="mistral:7b")

    if not result["success"]:
        print(f"❌ Failed: {result['error']}")
        return None

    print(f"✅ Answer generated in {result['latency_ms']:.0f}ms")
    print(f"Response length: {result['tokens']} tokens")

    # Step 4: Evaluate answer
    print(f"\n--- Step 4: Answer Evaluation ---")
    evaluation = evaluate_answer_quality(result["answer"], query)
    print(f"Quality: {evaluation['quality']} (score: {evaluation['score']}/100)")
    print(f"Has citation: {evaluation['has_citation']}")
    print(f"Has refusal: {evaluation['has_refusal']}")
    print(f"Word count: {evaluation['word_count']}")
    print(f"Avg sentence length: {evaluation['avg_sentence_length']} words")

    # Display answer
    print(f"\n--- Final Answer ---")
    print(result["answer"])

    # Return results
    total_time = retrieval_time + result["latency_ms"]
    return {
        "query": query,
        "retrieval_time_ms": retrieval_time,
        "generation_time_ms": result["latency_ms"],
        "total_time_ms": total_time,
        "answer": result["answer"],
        "evaluation": evaluation,
        "chunks_retrieved": len(relevant_chunks),
    }


async def main():
    """Run RAG test suite."""
    print("\n" + "=" * 80)
    print("LONG DOCUMENT RAG TEST SUITE")
    print("=" * 80)
    print("\nDocument length:", len(SAMPLE_DOCUMENT), "characters")

    # Test queries
    test_queries = [
        "What are the 5 consistency models offered by Cosmos DB?",
        "How should I choose a partition key for Cosmos DB?",
        "What are the cost optimization strategies for Cosmos DB?",
        "How does the Change Feed feature work?",
        "What is the maximum size of a logical partition?",
    ]

    results = []

    for i, query in enumerate(test_queries, 1):
        print(f"\n\n{'#' * 80}")
        print(f"TEST {i}/{len(test_queries)}")
        print(f"{'#' * 80}")

        result = await test_rag_pipeline(query, SAMPLE_DOCUMENT)
        if result:
            results.append(result)

        # Pause between tests
        if i < len(test_queries):
            await asyncio.sleep(2)

    # Summary
    print(f"\n\n{'=' * 80}")
    print("RAG PIPELINE SUMMARY")
    print(f"{'=' * 80}\n")

    print(
        f"{'Test':<5} {'Quality':<10} {'Retrieval':<12} {'Generation':<12} {'Total':<12} {'Citation'}"
    )
    print("-" * 80)

    for i, result in enumerate(results, 1):
        eval_data = result["evaluation"]
        print(
            f"{i:<5} "
            f"{eval_data['quality']:<10} "
            f"{result['retrieval_time_ms']:<12.0f} "
            f"{result['generation_time_ms']:<12.0f} "
            f"{result['total_time_ms']:<12.0f} "
            f"{'✅' if eval_data['has_citation'] else '❌'}"
        )

    # Calculate averages
    if results:
        avg_retrieval = sum(r["retrieval_time_ms"] for r in results) / len(results)
        avg_generation = sum(r["generation_time_ms"] for r in results) / len(results)
        avg_total = sum(r["total_time_ms"] for r in results) / len(results)

        print("-" * 80)
        print(
            f"{'AVG':<5} {'':<10} {avg_retrieval:<12.0f} {avg_generation:<12.0f} {avg_total:<12.0f}"
        )

    # Quality distribution
    print(f"\n{'=' * 80}")
    print("QUALITY DISTRIBUTION")
    print(f"{'=' * 80}\n")

    quality_counts = {"GOOD": 0, "FAIR": 0, "POOR": 0}
    for result in results:
        quality_counts[result["evaluation"]["quality"]] += 1

    total = len(results)
    for quality, count in quality_counts.items():
        pct = (count / total * 100) if total > 0 else 0
        print(f"{quality}: {count}/{total} ({pct:.0f}%)")

    # Save results
    output = {
        "test_date": "2025-12-01",
        "document_length": len(SAMPLE_DOCUMENT),
        "results": results,
    }

    with open("rag_test_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n📊 Results saved to: rag_test_results.json\n")


if __name__ == "__main__":
    asyncio.run(main())
