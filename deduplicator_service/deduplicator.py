#!/usr/bin/env python3

import logging
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class ArticleDeduplicator:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.sentence_model = None
        self._load_model()

    def _load_model(self):
        try:
            logger.info("Loading models sentence-transformers...")
            self.sentence_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("The model for embeddings has been successfully loaded.")
        except Exception as e:
            logger.error(f"Unable to load the embedding model: {e}")
            raise RuntimeError(f"Failed to initialize the embeddings model: {e}")

    def get_embedding_text(self, article: Dict) -> str:
        title = article.get('title', '')

        summary = article.get('summary', '')
        if not summary:
            summary = article.get('description', '')

        if summary:
            summary = summary[:200]

        embedding_text = f"{title}. {summary}".strip()

        return embedding_text

    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not text or not self.sentence_model:
            return None

        try:
            embedding = self.sentence_model.encode([text])
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            return None

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        try:
            emb1 = np.array(embedding1).reshape(1, -1)
            emb2 = np.array(embedding2).reshape(1, -1)
            similarity = cosine_similarity(emb1, emb2)[0][0]
            return float(similarity)
        except Exception as e:
            logger.error(f"Error in calculating similarity: {e}")
            return 0.0

    def deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        if not articles:
            return articles

        logger.info(f"Starting deduplication of {len(articles)} articles with a threshold {self.similarity_threshold}")

        unique_articles = []
        processed_embeddings = []

        for i, article in enumerate(articles):
            try:
                embedding_text = self.get_embedding_text(article)
                if not embedding_text:
                    logger.warning(f"Empty text for article {i}, skip")
                    continue

                embedding = self.get_embedding(embedding_text)
                if not embedding:
                    logger.warning(f"Unable to create an embedding for article  {i}, adding as unique")
                    unique_articles.append(article)
                    continue

                is_duplicate = False
                max_similarity = 0.0
                duplicate_index = -1

                for j, existing_embedding in enumerate(processed_embeddings):
                    similarity = self.calculate_similarity(embedding, existing_embedding)

                    if similarity > max_similarity:
                        max_similarity = similarity
                        duplicate_index = j

                    if similarity > self.similarity_threshold:
                        is_duplicate = True
                        logger.info(f"Duplicate found: article {i}s similar to article {j} "
                                  f"(similarity: {similarity:.3f})")
                        logger.debug(f"Duplicate title: {article.get('title', '')[:50]}...")
                        break

                if not is_duplicate:
                    unique_articles.append(article)
                    processed_embeddings.append(embedding)
                    logger.debug(f"Article {i} added as unique "
                               f"(max similarity: {max_similarity:.3f})")
                else:
                    original_title = unique_articles[duplicate_index].get('title', '')[:50] if duplicate_index < len(unique_articles) else 'unknown'
                    duplicate_title = article.get('title', '')[:50]
                    logger.info(f"Duplicate deleted: '{duplicate_title}...' is similar to '{original_title}...'")

            except Exception as e:
                logger.error(f"Error while processing the article {i}: {e}")
                unique_articles.append(article)

        removed_count = len(articles) - len(unique_articles)
        logger.info(f"Removal complete: {removed_count} duplicates removed. "
                   f"There are {len(unique_articles)} unique articles left")

        return unique_articles

    def get_similarity_matrix(self, articles: List[Dict]) -> List[List[float]]:
        if not articles:
            return []

        embeddings = []
        for article in articles:
            embedding_text = self.get_embedding_text(article)
            embedding = self.get_embedding(embedding_text)
            if embedding:
                embeddings.append(embedding)
            else:
                embeddings.append([0.0] * 384)

        similarity_matrix = []
        for i, emb1 in enumerate(embeddings):
            row = []
            for j, emb2 in enumerate(embeddings):
                if i == j:
                    row.append(1.0)
                else:
                    similarity = self.calculate_similarity(emb1, emb2)
                    row.append(similarity)
            similarity_matrix.append(row)

        return similarity_matrix
