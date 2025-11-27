from datasets import Dataset
from typing import Dict, Any
from dataclasses import dataclass, asdict
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, LLMContextPrecisionWithoutReference
from ragas.llms import LlamaIndexLLMWrapper
from ragas.embeddings import LlamaIndexEmbeddingsWrapper
import logging
import math
from ragas.run_config import RunConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    faithfulness_score: float
    answer_relevance_score: float
    context_precision_score: float
    overall_score: float
    error: bool = False
    error_message: str = ""
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def has_nan_values(scores) -> bool:
    if not isinstance(scores, dict):
        return True
    for key in ["faithfulness", "answer_relevancy", "llm_context_precision_without_reference"]:
        value = scores.get(key)
        if value is None:
            return True
        if isinstance(value, (int, float)) and (math.isnan(value) or math.isinf(value)):
            return True
    return False

async def evaluate_with_retry(question, answer, contexts, settings, max_retries=3) -> EvaluationResult:
    for attempt in range(max_retries):
        try:
            dataset = Dataset.from_dict({
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            })
            config = RunConfig(
                max_wait=45,
                timeout=600,
            )
            llm = LlamaIndexLLMWrapper(settings.llm)
            embeddings = LlamaIndexEmbeddingsWrapper(settings.embed_model)
            faith = Faithfulness(llm=llm)
            ar = AnswerRelevancy(llm=llm, embeddings=embeddings)
            prec = LLMContextPrecisionWithoutReference(llm=llm)
            scores = evaluate(llm=llm, dataset=dataset, metrics=[faith,ar,prec], run_config=config).scores[0]
            if has_nan_values(scores):
                logger.warning(f"Attempt {attempt + 1}: NaN values detected, retrying...")
                continue
            faithfulness = float(f'{scores["faithfulness"]:.3f}')
            relevance = float(f'{scores["answer_relevancy"]:.3f}')
            precision = float(f'{scores["llm_context_precision_without_reference"]:.3f}')
            overall_score = (faithfulness + relevance + precision) / 3
            return EvaluationResult(
                faithfulness_score=faithfulness,
                answer_relevance_score=relevance,
                context_precision_score=precision,
                overall_score=overall_score,
                error=False,
                error_message=""
            )
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            continue
    return EvaluationResult(
        faithfulness_score=0.0,
        answer_relevance_score=0.0,
        context_precision_score=0.0,
        overall_score=0.0,
        error=True,
        error_message="Ошибка при оценке качества - максимум попыток"
    )

async def evaluate_qa_pair(question, answer, contexts, settings) -> Dict[str, Any]:
    logger.info(f"Evaluating Q&A pair: {question[:100]}...")
    result = await evaluate_with_retry(question, answer, contexts, settings)
    if result.error:
        logger.error(f"Evaluation failed: {result.error_message}")
    else:
        logger.info(f"Evaluation complete. Overall score: {result.overall_score:.3f}")
    return result.to_dict()