import unittest

from src.prepare_data import split_data


class SplitTest(unittest.TestCase):
    def test_same_article_never_appears_in_both_groups(self):
        metadata = [
            {"article_id": f"article_{number}", "title": "", "keywords": "",
             "mesh_terms": "", "major_mesh_terms": ""}
            for number in range(10)
        ]
        cases = [
            {"case_id": f"case_{number}", "article_id": f"article_{number}",
             "case_text": "", "age": "", "gender": ""}
            for number in range(10)
        ]
        cases.append(
            {"case_id": "case_extra", "article_id": "article_0",
             "case_text": "", "age": "", "gender": ""}
        )

        development, evaluation = split_data(cases, metadata)
        development_articles = {record["article_id"] for record in development}
        evaluation_articles = {record["article_id"] for record in evaluation}

        self.assertTrue(development_articles.isdisjoint(evaluation_articles))
        self.assertEqual(development_articles | evaluation_articles,
                         {article["article_id"] for article in metadata})
        self.assertEqual(len(evaluation_articles), 2)
        self.assertEqual(len(development) + len(evaluation), len(cases))


if __name__ == "__main__":
    unittest.main()
