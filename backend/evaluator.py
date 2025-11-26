import numpy as np
from datasets import Dataset 
from typing import Dict, Any
from dataclasses import dataclass, asdict
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, LLMContextPrecisionWithoutReference
from ragas.llms import LlamaIndexLLMWrapper
from ragas.embeddings import LlamaIndexEmbeddingsWrapper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    faithfulness_score: float
    answer_relevance_score: float
    context_precision_score: float
    overall_score: float
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

async def evaluate_qa_pair(question, answer, contexts, settings) -> Dict[str, Any]:
    logger.info(f"Evaluating Q&A pair: {question[:100]}...")
    dataset = Dataset.from_dict({
        "question": [question],
        "answer": [answer],
        "contexts": [contexts],
    })
    llm = LlamaIndexLLMWrapper(settings.llm)
    embeddings = LlamaIndexEmbeddingsWrapper(settings.embed_model)
    faith = Faithfulness(llm=llm)
    ar = AnswerRelevancy(llm=llm, embeddings=embeddings)
    prec = LLMContextPrecisionWithoutReference(llm=llm)
    scores = evaluate(llm=llm, dataset=dataset, metrics=[faith,ar,prec]).scores[0]
    faithfulness = float(f'{scores["faithfulness"]:.3f}')
    relevance = float(f'{scores["answer_relevancy"]:.3f}')
    precision = float(f'{scores["llm_context_precision_without_reference"]:.3f}')
    overall_score = (faithfulness + relevance + precision) / 3
    result = EvaluationResult(
        faithfulness_score=faithfulness,
        answer_relevance_score=relevance,
        context_precision_score=precision,
        overall_score=overall_score,
    )
    logger.info(f"Evaluation complete. Overall score: {overall_score:.3f}")
    return result.to_dict()