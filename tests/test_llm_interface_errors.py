"""Tests for error_type field in ask_with_rag() — Task 6."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from src.rag.llm_interface import ask_with_rag


class TestAskWithRagErrorType(unittest.TestCase):

    @staticmethod
    def _make_chunk(distance: float, text: str = "some content", file_name: str = "doc.txt") -> dict:
        return {
            "id": "chunk_0",
            "text": text,
            "metadata": {"file_name": file_name, "file_path": "/data/doc.txt"},
            "distance": distance,
        }

    def test_no_chunks_returns_no_chunks_error_type(self):
        with patch("src.rag.llm_interface.similarity_search", return_value=[]):
            result = ask_with_rag(
                question="What is the policy?",
                llm=MagicMock(),
                persist_dir="fake/chroma",
            )
        self.assertEqual(result["error_type"], "no_chunks")
        self.assertEqual(result["answer"], "No searchable content found.")

    def test_low_similarity_returns_low_similarity_error_type(self):
        far_chunks = [
            self._make_chunk(0.85),
            self._make_chunk(0.91),
            self._make_chunk(0.99),
        ]
        with patch("src.rag.llm_interface.similarity_search", return_value=far_chunks):
            result = ask_with_rag(
                question="What is the policy?",
                llm=MagicMock(),
                persist_dir="fake/chroma",
            )
        self.assertEqual(result["error_type"], "low_similarity")
        self.assertEqual(result["answer"], "Found content but nothing closely matched your question.")

    def test_successful_rag_returns_none_error_type(self):
        good_chunks = [
            self._make_chunk(0.2, text="The leave policy allows 20 days."),
            self._make_chunk(0.15, text="Annual leave resets each January."),
        ]
        with (
            patch("src.rag.llm_interface.similarity_search", return_value=good_chunks),
            patch("src.rag.llm_interface._run_chain", return_value="answer text"),
        ):
            result = ask_with_rag(
                question="What is the policy?",
                llm=MagicMock(),
                persist_dir="fake/chroma",
            )
        self.assertIsNone(result["error_type"])
        self.assertEqual(result["answer"], "answer text")

    def test_ollama_timeout_returns_ollama_timeout_error_type(self):
        good_chunks = [self._make_chunk(0.2, text="The leave policy allows 20 days.")]
        with (
            patch("src.rag.llm_interface.similarity_search", return_value=good_chunks),
            patch("src.rag.llm_interface._run_chain", side_effect=httpx.TimeoutException("timed out")),
        ):
            result = ask_with_rag(
                question="What is the policy?",
                llm=MagicMock(),
                persist_dir="fake/chroma",
            )
        self.assertEqual(result["error_type"], "ollama_timeout")
        self.assertEqual(result["answer"], "Ollama took too long to respond.")

    def test_result_has_sources_list(self):
        good_chunks = [self._make_chunk(0.2, text="Some text.", file_name="report.pdf")]
        with (
            patch("src.rag.llm_interface.similarity_search", return_value=good_chunks),
            patch("src.rag.llm_interface._run_chain", return_value="some answer"),
        ):
            result = ask_with_rag(
                question="Tell me about the report.",
                llm=MagicMock(),
                persist_dir="fake/chroma",
            )
        self.assertIn("sources", result)
        self.assertIsInstance(result["sources"], list)

    def test_no_chunks_has_empty_sources(self):
        with patch("src.rag.llm_interface.similarity_search", return_value=[]):
            result = ask_with_rag(
                question="What is the policy?",
                llm=MagicMock(),
                persist_dir="fake/chroma",
            )
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
