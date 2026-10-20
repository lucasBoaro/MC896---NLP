import unittest

from src.build_graph import build_graph, prepare_entries


class BuildGraphTest(unittest.TestCase):
    def setUp(self):
        self.lexicon = prepare_entries([
            {"term": "pain", "type": "Symptom", "canonical": "pain", "source": "manual"},
            {"term": "aspirin", "type": "Treatment", "canonical": "aspirin", "source": "manual"},
            {"term": "pantoprazole", "type": "Treatment", "canonical": "pantoprazole", "source": "manual"},
            {"term": "prednisone", "type": "Treatment", "canonical": "prednisone", "source": "manual"},
            {"term": "diltiazem", "type": "Treatment", "canonical": "diltiazem", "source": "manual"},
            {"term": "CAS", "type": "Condition", "canonical": "coronary artery spasm", "source": "manual"},
            {"term": "computed tomography", "type": "Exam", "canonical": "computed tomography", "source": "manual"},
            {"term": "CT", "type": "Exam", "canonical": "computed tomography", "source": "manual"},
            {"term": "CAG", "type": "Exam", "canonical": "coronary angiography", "source": "manual"},
            {"term": "ECG", "type": "Exam", "canonical": "electrocardiogram", "source": "manual"},
            {"term": "acute coronary syndrome", "type": "Condition", "canonical": "acute coronary syndrome", "source": "manual"},
            {"term": "hypertension", "type": "Condition", "canonical": "hypertension", "source": "manual"},
            {"term": "pneumonia", "type": "Condition", "canonical": "pneumonia", "source": "manual"},
        ], "term")
        self.triggers = prepare_entries([
            {"phrase": "presented with", "kind": "relation", "value": "HAS_SYMPTOM"},
            {"phrase": "treated with", "kind": "relation", "value": "RECEIVED_TREATMENT"},
            {"phrase": "revealed", "kind": "relation", "value": "INDICATES"},
            {"phrase": "no", "kind": "negation", "value": "NEGATED"},
            {"phrase": "possible", "kind": "uncertainty", "value": "SUSPECTED"},
            {"phrase": "cannot be excluded", "kind": "uncertainty", "value": "SUSPECTED"},
            {"phrase": "resolution of", "kind": "resolution", "value": "RESOLVED"},
            {"phrase": "was suggested", "kind": "not_performed", "value": "NOT_PERFORMED"},
            {"phrase": "was refused", "kind": "not_performed", "value": "NOT_PERFORMED"},
            {"phrase": "to treat", "kind": "treatment_target", "value": "TREATS"},
            {"phrase": "treatment for", "kind": "treatment_target", "value": "TREATS"},
        ], "phrase")

    def test_creates_case_entity_nodes_and_edges(self):
        cases = [{
            "case_id": "c1", "article_id": "a1", "age": "44", "gender": "female",
            "title": "Example", "case_text": "Presented with pain. Two days later, treated with aspirin 500 mg.",
        }]
        nodes, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual([n["type"] for n in nodes], ["Case", "Symptom", "Treatment"])
        self.assertIn("dose", nodes[-1]["attributes"])
        self.assertIn("time", nodes[-1]["attributes"])
        self.assertIn("BEFORE", [edge["relation"] for edge in edges])

    def test_negated_entity_is_not_added(self):
        cases = [{
            "case_id": "c1", "article_id": "a1", "age": "", "gender": "",
            "title": "", "case_text": "The patient had no pain.",
        }]
        nodes, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(edges, [])

    def test_name_and_nearby_abbreviation_create_one_node(self):
        cases = [{
            "case_id": "c1", "case_text": "Computed tomography (CT) was performed."
        }]
        nodes, _ = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual([node["type"] for node in nodes].count("Exam"), 1)

    def test_dose_is_attached_only_to_nearby_treatment(self):
        cases = [{
            "case_id": "c1",
            "case_text": "Pantoprazole (40 mg) was used to prevent injury caused by prednisone."
        }]
        nodes, _ = build_graph(cases, self.lexicon, self.triggers)
        treatments = {node["label"]: node["attributes"] for node in nodes if node["type"] == "Treatment"}
        self.assertEqual(treatments["pantoprazole"]["dose"], "40 mg")
        self.assertNotIn("dose", treatments["prednisone"])

    def test_uncertainty_does_not_cross_comma(self):
        cases = [{
            "case_id": "c1",
            "case_text": "With a possible diagnosis of CAS, 5 mg of diltiazem was administered."
        }]
        nodes, _ = build_graph(cases, self.lexicon, self.triggers)
        assertions = {node["label"]: node["attributes"]["assertion"] for node in nodes if node["type"] != "Case"}
        self.assertEqual(assertions["coronary artery spasm"], "suspected")
        self.assertEqual(assertions["diltiazem"], "affirmed")

    def test_resolved_and_refused_mentions_are_not_facts(self):
        cases = [{
            "case_id": "c1",
            "case_text": "There was complete resolution of pain. CAG was suggested but was refused."
        }]
        nodes, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(edges, [])

    def test_condition_of_other_person_is_not_added(self):
        cases = [{
            "case_id": "c1", "case_text": "The patient's mother had hypertension."
        }]
        nodes, _ = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual(len(nodes), 1)

    def test_before_expression_does_not_create_forward_edge(self):
        cases = [{
            "case_id": "c1", "case_text": "The patient had pain. CT before admission was normal."
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertNotIn("BEFORE", [edge["relation"] for edge in edges])

    def test_before_does_not_connect_the_same_concept_to_itself(self):
        cases = [{
            "case_id": "c1",
            "case_text": "Aspirin was given. Two days later, aspirin was given again.",
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertNotIn("BEFORE", [edge["relation"] for edge in edges])

    def test_anchored_time_is_not_attached_to_the_previous_entity(self):
        cases = [{
            "case_id": "c1",
            "case_text": "Aspirin was given. CT was performed two days after admission.",
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertNotIn("BEFORE", [edge["relation"] for edge in edges])

    def test_mid_sentence_later_does_not_reuse_unrelated_previous_entity(self):
        cases = [{
            "case_id": "c1",
            "case_text": (
                "Aspirin was given. The discussion noted that the patient stopped "
                "smoking, and hypertension appeared four months later."
            ),
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertNotIn("BEFORE", [edge["relation"] for edge in edges])

    def test_indicates_requires_exam_trigger_condition_order(self):
        cases = [{
            "case_id": "c1",
            "case_text": (
                "Computed tomography revealed a 12.5 mm finding consistent with "
                "pneumonia."
            ),
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual(
            [edge["relation"] for edge in edges].count("INDICATES"), 1
        )

    def test_condition_before_result_trigger_is_not_indicated_by_exam(self):
        cases = [{
            "case_id": "c1",
            "case_text": (
                "Acute coronary syndrome was considered, and computed tomography "
                "revealed nonspecific opacities."
            ),
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertNotIn("INDICATES", [edge["relation"] for edge in edges])

    def test_uncertainty_can_follow_condition(self):
        cases = [{
            "case_id": "c1",
            "case_text": "Acute coronary syndrome cannot be excluded."
        }]
        nodes, _ = build_graph(cases, self.lexicon, self.triggers)
        condition = next(node for node in nodes if node["type"] == "Condition")
        self.assertEqual(condition["attributes"]["assertion"], "suspected")

    def test_measurement_is_not_attached_to_unrelated_exam(self):
        cases = [{
            "case_id": "c1", "case_text": "Troponin was 0.031 ng/mL and ECG was normal."
        }]
        nodes, _ = build_graph(cases, self.lexicon, self.triggers)
        exam = next(node for node in nodes if node["type"] == "Exam")
        self.assertNotIn("measurement", exam["attributes"])

    def test_treats_requires_explicit_evidence(self):
        cases = [{
            "case_id": "c1", "case_text": "Aspirin was given to treat pneumonia."
        }]
        nodes, edges = build_graph(cases, self.lexicon, self.triggers)
        treats = [edge for edge in edges if edge["relation"] == "TREATS"]
        self.assertEqual(len(treats), 1)
        source = next(node for node in nodes if node["node_id"] == treats[0]["source_id"])
        target = next(node for node in nodes if node["node_id"] == treats[0]["target_id"])
        self.assertEqual(source["type"], "Treatment")
        self.assertEqual(target["type"], "Condition")

    def test_cooccurrence_alone_does_not_create_treats(self):
        cases = [{
            "case_id": "c1", "case_text": "The patient had pneumonia and used aspirin."
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertNotIn("TREATS", [edge["relation"] for edge in edges])

    def test_treatment_for_creates_treats(self):
        cases = [{
            "case_id": "c1", "case_text": "The treatment for pneumonia was aspirin."
        }]
        _, edges = build_graph(cases, self.lexicon, self.triggers)
        self.assertEqual(
            [edge["relation"] for edge in edges].count("TREATS"), 1
        )


if __name__ == "__main__":
    unittest.main()
