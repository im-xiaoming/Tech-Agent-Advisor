from django.test import TestCase

from evaluation.models import RagEvaluation


class RagEvaluationModelTests(TestCase):
    def test_average_score_ignores_none(self):
        evaluation = RagEvaluation(
            question="q",
            answer="a",
            faithfulness=1.0,
            answer_relevancy=0.5,
            context_precision=None,
            context_recall=None,
        )
        self.assertAlmostEqual(evaluation.average_score, 0.75)

    def test_average_score_none_when_empty(self):
        self.assertIsNone(RagEvaluation(question="q").average_score)
