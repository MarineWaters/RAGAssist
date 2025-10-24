import asyncio
from ragas.testset import TestsetGenerator
from ragas.llms import LlamaIndexLLMWrapper
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
import pandas as pd
from main import query as rag_query

def generate_testset(llm_model, llm_embed_model, documents, testset_size=5):
    try:
        embeddings = LlamaIndexLLMWrapper(llm_embed_model)
        llm = LlamaIndexLLMWrapper(llm_model)
        generator = TestsetGenerator.from_llama_index(
            llm=llm,
            embedding_model=embeddings,
        )
        testset = generator.generate_with_llamaindex_docs(
            documents,
            testset_size=testset_size,
        )
        return testset
    except Exception as e:
        print(f"❌ Error generating testset: {e}")
        raise e

async def evaluate_rag(testset, llm_model):
    try:
        questions = []
        answers = []
        contexts = []
        ground_truths = []
        for sample in testset.samples:
            question = sample.eval_sample.question
            ground_truth = sample.eval_sample.reference_answer
            rag_answer = await rag_query(question, mode="vector")
            context = [""] 
            questions.append(question)
            answers.append(rag_answer)
            contexts.append(context)
            ground_truths.append(ground_truth)

        dataset = pd.DataFrame({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths
        })
        result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
            ],
            llm=llm_model,
        )
        return {
            "scores": result.scores.to_dict(),
            "dataset": dataset.to_dict('records'),
            "overall_scores": {
                "faithfulness": result["faithfulness"].mean(),
                "answer_relevancy": result["answer_relevancy"].mean(),
                "context_precision": result["context_precision"].mean()
            }
        }
    except Exception as e:
        print(f"❌ Error evaluating RAG: {e}")
        raise e

async def run_evaluation(llm_model, llm_embed_model, documents, testset_size=5):
    testset = generate_testset(llm_model, llm_embed_model, documents, testset_size)
    evaluation_results = await evaluate_rag(testset, llm_model)
    print("✅ Evaluation completed")
    return evaluation_results