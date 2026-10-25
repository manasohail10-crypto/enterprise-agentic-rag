import importlib
import math
import sys
import types
import warnings

import requests
from langchain_core.embeddings import Embeddings

from app.config import setting
from app.gateway.client import get_langchain_llm

warnings.filterwarnings("ignore", message="Unexpected type for token usage")

JINA_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"
SHORT_NAMES = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "relevancy",
    "llm_context_precision_with_reference": "precision",
    "context_recall": "recall",
}
METRIC_NAMES = {
    "faithfulness": "Faithfulness (answer only uses the context)",
    "answer_relevancy": "Answer relevancy (answer fits the question)",
    "llm_context_precision_with_reference": "Context precision (good passages come first)",
    "context_recall": "Context recall (context has what is needed)",
}


class JinaEmbeddings(Embeddings):
    def _embed(self, texts, task):
        response = requests.post(
            JINA_URL,
            headers={"Authorization": f"Bearer {setting.JINA_API_KEY}"},
            json={"model": JINA_MODEL, "task": task, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        return [item["embedding"] for item in response.json()["data"]]

    def embed_documents(self, texts):
        return self._embed(list(texts), "text-matching")

    def embed_query(self, text):
        return self._embed([text], "text-matching")[0]


def stub_missing_vertex_module(name):
    module = types.ModuleType(name)
    module.__getattr__ = lambda attr: type(attr, (), {})
    sys.modules[name] = module
    parent, _, child = name.rpartition(".")
    if parent in sys.modules:
        setattr(sys.modules[parent], child, module)


def load_ragas():
    for _ in range(6):
        try:
            for name in [k for k in sys.modules if k == "ragas" or k.startswith("ragas.")]:
                del sys.modules[name]
            return importlib.import_module("ragas")
        except ModuleNotFoundError as error:
            missing = error.name or ""
            if "vertexai" not in missing:
                raise
            stub_missing_vertex_module(missing)
    raise ImportError("ragas could not be loaded")


def pick_rows(rows):
    return [
        row
        for row in rows
        if row["type"] == "covered"
        and not row["error"]
        and not row["blocked"]
        and row["answer"]
        and row["contexts"]
        and not row["web_sources"]
    ]


def average(values):
    clean = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return round(sum(clean) / len(clean), 3) if clean else None


def score_rows(rows):
    picked = pick_rows(rows)
    print("\n" + "=" * 70)
    print("RAGAS (AI judge)")
    print("=" * 70)

    if not picked:
        print("  No covered answers with document passages to score.")
        return None

    try:
        load_ragas()
        from ragas import EvaluationDataset, RunConfig, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
            ResponseRelevancy,
        )
    except ImportError as error:
        print(f"  RAGAS could not be imported: {error}")
        return None

    print(f"  Scoring {len(picked)} answers (this is slow, the judge makes many calls)...")

    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": row["question"],
                "response": row["answer"],
                "retrieved_contexts": row["contexts"],
                "reference": row["ground_truth"],
            }
            for row in picked
        ]
    )

    llm = get_langchain_llm(feature="ragas_judge")
    try:
        judge = LangchainLLMWrapper(llm, bypass_n=True)
        strictness = 3
    except TypeError:
        judge = LangchainLLMWrapper(llm)
        strictness = 1
    embeddings = LangchainEmbeddingsWrapper(JinaEmbeddings())

    try:
        result = evaluate(
            dataset=dataset,
            metrics=[
                Faithfulness(),
                ResponseRelevancy(strictness=strictness),
                LLMContextPrecisionWithReference(),
                LLMContextRecall(),
            ],
            llm=judge,
            embeddings=embeddings,
            run_config=RunConfig(max_workers=2, timeout=180, max_retries=5),
            raise_exceptions=False,
            show_progress=True,
        )
    except Exception as error:
        print(f"  RAGAS failed: {type(error).__name__}: {error}")
        return None

    table = result.to_pandas()
    metric_columns = [c for c in table.columns if c in METRIC_NAMES]

    per_row = []
    for row, (_, scores) in zip(picked, table.iterrows()):
        per_row.append({"id": row["id"], **{c: (None if scores[c] != scores[c] else round(float(scores[c]), 3)) for c in metric_columns}})

    averages = {c: average(table[c].tolist()) for c in metric_columns}

    print()
    for column in metric_columns:
        value = averages[column]
        shown = "no score" if value is None else f"{value:.2f}"
        print(f"  {METRIC_NAMES[column]:<52} {shown}")

    weak = [
        r for r in per_row
        if any(r[c] is not None and r[c] < 0.7 for c in metric_columns)
    ]
    if weak:
        print("\n  Answers with a score under 0.70 (look at these first):")
        for r in weak:
            low = ", ".join(f"{SHORT_NAMES[c]} {r[c]:.2f}" for c in metric_columns if r[c] is not None and r[c] < 0.7)
            print(f"    {r['id']}  {low}")

    return {"scored": len(picked), "average": averages, "per_question": per_row}