"""Gera os nós e as arestas do grafo a partir dos casos clínicos."""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "prepared" / "all_cases.csv"
DEFAULT_NODES = ROOT / "outputs" / "full" / "v2" / "nodes.csv"
DEFAULT_EDGES = ROOT / "outputs" / "full" / "v2" / "edges.csv"
LEXICON_PATH = ROOT / "resources" / "v2" / "lexicon.csv"
TRIGGERS_PATH = ROOT / "resources" / "v2" / "triggers.csv"

CASE_RELATIONS = {
    "Symptom": "HAS_SYMPTOM",
    "Exam": "UNDERWENT_EXAM",
    "Condition": "DIAGNOSED_WITH",
    "Treatment": "RECEIVED_TREATMENT",
}

NODE_FIELDS = [
    "node_id", "case_id", "type", "label", "mention_text",
    "sentence_id", "start", "end", "attributes", "evidence",
]
EDGE_FIELDS = [
    "edge_id", "case_id", "source_id", "target_id", "relation",
    "attributes", "evidence",
]

SENTENCE_SEPARATOR = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n+")
NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
)
NUMERIC_VALUE = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)"
NUMBER = rf"(?:{NUMERIC_VALUE}|{NUMBER_WORDS})"
TIME_UNIT = r"(?:minutes?|hours?|days?|weeks?|months?|years?|h)"
MONTH = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)

PATTERNS = {
    "dose": re.compile(
        rf"(?<![\w.])(?P<value>{NUMERIC_VALUE})\s*"
        rf"(?P<unit>mcg|µg|mg|g|mL)"
        rf"(?P<rate>(?:\s*/\s*(?:kg|day|d|hour|h)){{0,2}})"
        rf"(?!\s*(?:/\s*(?:dL|L|min(?:ute)?)|%))\b",
        re.IGNORECASE,
    ),
    "measurement": re.compile(
        rf"(?<![\w.])(?P<value>{NUMERIC_VALUE}(?:/{NUMERIC_VALUE})?)\s*"
        r"(?P<unit>mg/dL|g/dL|mmol/L|ng/mL|IU/L|IU/mL|AU/mL|U/L|"
        r"microg/L|mL/min(?:ute)?|L/min|mm\s*Hg|"
        r"(?:beats|breaths)\s*(?:per|/)\s*min(?:ute)?s?|"
        r"/min(?:ute)?|bpm|°\s*C|(?<=\s)C)\b",
        re.IGNORECASE,
    ),
    "relative_time": re.compile(
        rf"\b(?:"
        rf"(?P<quantity>{NUMBER})\s+(?P<unit>{TIME_UNIT})\s+"
        rf"(?P<direction>later|after|before|prior\s+to)"
        rf"(?:\s+(?P<reference>admission|surgery|operation|diagnosis|treatment|discharge))?"
        rf"|(?P<sequence>the\s+(?:following|next)\s+day)"
        rf"|(?P<prefix_direction>after|before)\s+"
        rf"(?P<prefix_quantity>{NUMBER})\s+(?P<prefix_unit>{TIME_UNIT})"
        rf"|(?P<anchor_direction>after|before)\s+"
        rf"(?P<anchor>admission|hospitalization|surgery|operation|diagnosis|treatment|discharge)"
        rf"|(?:on\s+)?(?:the\s+)?(?P<hospital_day>\d+(?:st|nd|rd|th)?)\s+"
        rf"day\s+of\s+(?P<hospital_anchor>hospitalization|admission)"
        rf"|day\s+(?P<hospital_day_number>\d+)\s+of\s+"
        rf"(?P<hospital_day_number_anchor>hospitalization|admission)"
        rf"|(?P<pod_label>POD|postoperative\s+day)\s*(?P<pod_day>\d+)"
        rf")\b",
        re.IGNORECASE,
    ),
    "duration": re.compile(
        rf"\b(?P<prefix>for|during|over(?:\s+a\s+period\s+of)?)\s+"
        rf"(?:the\s+past\s+)?(?P<quantity>{NUMBER})\s+"
        rf"(?:consecutive\s+)?(?P<unit>{TIME_UNIT})"
        rf"(?!\s+(?:later|after|before|prior\s+to))\b",
        re.IGNORECASE,
    ),
    "history_duration": re.compile(
        rf"\b(?:a\s+)?(?P<quantity>{NUMBER})[ -]"
        rf"(?P<unit>minute|hour|day|week|month|year)(?:-|\s+)history\b",
        re.IGNORECASE,
    ),
    "absolute_date": re.compile(
        rf"\b(?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?|"
        rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}\s+\d{{4}}|"
        rf"{MONTH}\s+\d{{4}})\b",
        re.IGNORECASE,
    ),
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def prepare_entries(entries, phrase_field):
    prepared = []
    for entry in entries:
        item = dict(entry)
        phrase = item[phrase_field]
        item["_pattern"] = re.compile(
            rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE
        )
        prepared.append(item)
    return sorted(
        prepared,
        key=lambda item: (-len(item[phrase_field].split()), -len(item[phrase_field])),
    )


def _split_sentences(text):
    sentences = []
    start = 0
    for separator in SENTENCE_SEPARATOR.finditer(text):
        _append_sentence(sentences, text, start, separator.start())
        start = separator.end()
    _append_sentence(sentences, text, start, len(text))
    for sentence_id, sentence in enumerate(sentences):
        sentence["sentence_id"] = sentence_id
    return sentences


def _append_sentence(sentences, text, start, end):
    segment = text[start:end]
    clean = segment.strip()
    if clean:
        clean_start = start + len(segment) - len(segment.lstrip())
        sentences.append({"text": clean, "start": clean_start})


def _phrase_matches(text, entries):
    matches = []
    occupied = []
    for entry in entries:
        for match in entry["_pattern"].finditer(text):
            span = (match.start(), match.end())
            if any(span[0] < end and start < span[1] for start, end in occupied):
                continue
            occupied.append(span)
            matches.append({
                "entry": entry,
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
            })
    return sorted(matches, key=lambda item: (item["start"], item["end"]))


def _pattern_matches(text):
    matches = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            matches.append({
                "kind": kind,
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
            })
    return sorted(matches, key=lambda item: (item["start"], item["end"]))


def extract_case(case, lexicon, triggers):
    """Localiza entidades, gatilhos e padrões de um caso."""
    results = []
    for sentence in _split_sentences(case["case_text"]):
        base = {
            "case_id": case["case_id"],
            "sentence_id": sentence["sentence_id"],
            "sentence_text": sentence["text"],
            "sentence_start": sentence["start"],
        }
        for match in _phrase_matches(sentence["text"], lexicon):
            entry = match["entry"]
            results.append({
                **base,
                "match_kind": "entity",
                "match_text": match["text"],
                "match_type": entry["type"],
                "normalized_value": entry["canonical"],
                "start": sentence["start"] + match["start"],
                "end": sentence["start"] + match["end"],
                "attributes": {"source": entry["source"]},
            })
        for match in _phrase_matches(sentence["text"], triggers):
            entry = match["entry"]
            results.append({
                **base,
                "match_kind": "trigger",
                "match_text": match["text"],
                "match_type": entry["kind"],
                "normalized_value": entry["value"],
                "start": sentence["start"] + match["start"],
                "end": sentence["start"] + match["end"],
                "attributes": {},
            })
        for match in _pattern_matches(sentence["text"]):
            results.append({
                **base,
                "match_kind": "pattern",
                "match_text": match["text"],
                "match_type": match["kind"],
                "normalized_value": "",
                "start": sentence["start"] + match["start"],
                "end": sentence["start"] + match["end"],
                "attributes": {},
            })
    return sorted(results, key=lambda item: (item["sentence_id"], item["start"]))


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _local_start(item):
    """Posição exata do item dentro de sua frase."""
    return item["start"] - item["sentence_start"]


def _scope_trigger(entity, triggers, kind, max_distance=80, allow_after=False):
    """Busca um gatilho local sem atravessar uma oração."""
    entity_start = _local_start(entity)
    entity_end = entity["end"] - entity["sentence_start"]
    candidates = []
    for trigger in triggers:
        if trigger["match_type"] != kind:
            continue
        trigger_start = _local_start(trigger)
        trigger_end = trigger["end"] - trigger["sentence_start"]
        if trigger_end <= entity_start:
            distance = entity_start - trigger_end
            between = entity["sentence_text"][trigger_end:entity_start]
        elif allow_after and entity_end <= trigger_start:
            distance = trigger_start - entity_end
            between = entity["sentence_text"][entity_end:trigger_start]
        else:
            continue
        blocked = any(mark in between for mark in ".;:")
        blocked = blocked or bool(re.search(r"\b(?:but|however|although)\b", between, re.I))
        if kind == "uncertainty" and "," in between:
            blocked = True
        if distance <= max_distance and not blocked:
            candidates.append((distance, trigger))
    return min(candidates, default=(None, None), key=lambda item: item[0])[1]


def _deduplicate_aliases(entities):
    """Remove sigla e nome completo quando representam a mesma menção."""
    kept = []
    for entity in sorted(entities, key=lambda item: item["start"]):
        duplicate_index = None
        for index, previous in enumerate(kept):
            same_concept = (
                previous["match_type"] == entity["match_type"]
                and previous["normalized_value"] == entity["normalized_value"]
            )
            gap = entity["start"] - previous["end"]
            has_abbreviation = (
                len(previous["match_text"]) <= 8 or len(entity["match_text"]) <= 8
            )
            if same_concept and 0 <= gap <= 60 and has_abbreviation:
                duplicate_index = index
                break
        if duplicate_index is None:
            kept.append(entity)
        elif len(entity["match_text"]) > len(kept[duplicate_index]["match_text"]):
            kept[duplicate_index] = entity
    return sorted(kept, key=lambda item: item["start"])


def _mentions_other_person(entity):
    """Evita transformar condições de familiares em condições do paciente."""
    start = _local_start(entity)
    prefix = entity["sentence_text"][:start].lower()
    window = prefix[-180:]
    other = list(re.finditer(
        r"\b(?:mother|maternal|father|paternal|husband|wife|sibling|family history)\b",
        window,
    ))
    if not other:
        return False
    after_subject = window[other[-1].end():]
    return not re.search(r"\b(?:patient|she|he|her|his)\b", after_subject)


def _nearby_pattern(entity, patterns, kind, before=20, after=25):
    """Associa valor somente quando ele está encostado na entidade."""
    candidates = []
    for pattern in patterns:
        if pattern["match_type"] != kind:
            continue
        if pattern["end"] <= entity["start"]:
            distance = entity["start"] - pattern["end"]
            allowed = before
            between = entity["sentence_text"][
                pattern["end"] - entity["sentence_start"]:_local_start(entity)
            ]
        elif entity["end"] <= pattern["start"]:
            distance = pattern["start"] - entity["end"]
            allowed = after
            between = entity["sentence_text"][
                entity["end"] - entity["sentence_start"]:
                pattern["start"] - entity["sentence_start"]
            ]
        else:
            distance = 0
            allowed = max(before, after)
            between = ""
        if kind == "dose" and not re.fullmatch(
            r"\s*(?:\(|\)|,|of|at|at\s+a\s+dose\s+of)*\s*",
            between,
            re.I,
        ):
            continue
        if distance <= allowed:
            candidates.append((distance, pattern))
    return min(candidates, default=(None, None), key=lambda item: item[0])[1]


def _entity_times(entity, patterns, triggers):
    """Seleciona apenas a referência temporal mais próxima da entidade."""
    time_patterns = [
        pattern for pattern in patterns
        if pattern["match_type"] in {
            "relative_time", "absolute_date", "duration", "history_duration"
        }
    ]
    values = []
    leading = []
    for pattern in time_patterns:
        prefix = entity["sentence_text"][:_local_start(pattern)].strip().lower()
        valid_prefix = bool(re.fullmatch(r"(?:on|at|by|after|before|the|in|during|\s)*", prefix))
        if valid_prefix and pattern["end"] <= entity["start"]:
            leading.append(pattern)
    if leading:
        values.append(leading[-1]["match_text"])

    ranked = []
    for pattern in time_patterns:
        distance = min(
            abs(entity["start"] - pattern["end"]),
            abs(pattern["start"] - entity["end"]),
        )
        if distance <= 80:
            ranked.append((distance, pattern))
    nearby = min(ranked, default=(None, None), key=lambda item: item[0])[1]
    if nearby and nearby["match_text"] not in values:
        values.append(nearby["match_text"])

    anchors = [
        trigger for trigger in triggers
        if trigger["match_type"] == "temporal_anchor"
        and _local_start(trigger) <= 35
    ]
    if anchors and anchors[-1]["match_text"] not in values:
        values.append(anchors[-1]["match_text"])
    return values


def _is_forward_time(text):
    """Aceita apenas referências que retomam o evento narrativo anterior.

    Expressões como ``after surgery`` e ``POD 3`` possuem uma âncora própria.
    Como essa âncora ainda não é representada por um nó, ligá-las ao último
    termo extraído criaria uma relação temporal inventada.
    """
    return bool(re.search(
        r"\b(?:later|the\s+(?:following|next)\s+day)\b",
        text,
        re.IGNORECASE,
    ))


def _nearest(item, candidates, max_distance=None):
    """Devolve o candidato mais próximo do item na mesma frase."""
    if not candidates:
        return None
    center = (item["start"] + item["end"]) / 2
    ranked = sorted(
        candidates,
        key=lambda candidate: abs(
            center - (candidate["start"] + candidate["end"]) / 2
        ),
    )
    chosen = ranked[0]
    distance = abs(center - (chosen["start"] + chosen["end"]) / 2)
    if max_distance is not None and distance > max_distance:
        return None
    return chosen


def _compatible_relation(entity_type, trigger):
    if trigger["match_type"] != "relation":
        return False
    return trigger["normalized_value"] == CASE_RELATIONS.get(entity_type)


def _near_nodes(item, nodes, max_distance=180):
    """Seleciona nós próximos ao gatilho dentro da mesma frase."""
    center = (item["start"] + item["end"]) / 2
    return [
        node for node in nodes
        if abs(center - (node["start"] + node["end"]) / 2) <= max_distance
    ]


def _bridged_pair(trigger, sources, targets, max_gap=350):
    """Encontra ``fonte -> gatilho -> destino`` na mesma oração.

    A simples presença de um exame e de uma condição na frase não demonstra
    que o resultado do exame indique aquela condição. A ordem e a proximidade
    tornam a ligação explícita e evitam associar uma suspeita mencionada antes
    do exame ao resultado descrito depois dele.
    """
    sentence_start = trigger["sentence_start"]
    text = trigger["sentence_text"]
    candidates = []
    for source in sources:
        source_gap = trigger["start"] - source["end"]
        if not 0 <= source_gap <= max_gap:
            continue
        before = text[source["end"] - sentence_start:trigger["start"] - sentence_start]
        if re.search(r"[;:]|(?<!\d)\.(?!\d)", before):
            continue
        for target in targets:
            target_gap = target["start"] - trigger["end"]
            if not 0 <= target_gap <= max_gap:
                continue
            after = text[trigger["end"] - sentence_start:target["start"] - sentence_start]
            if re.search(r"[;:]|(?<!\d)\.(?!\d)", after):
                continue
            candidates.append((source_gap + target_gap, source, target))
    if not candidates:
        return None, None
    _, source, target = min(candidates, key=lambda item: item[0])
    return source, target


def build_graph(cases, lexicon, triggers):
    """Extrai entidades e devolve listas de nós e arestas."""
    nodes = []
    edges = []
    node_count = 0
    edge_count = 0

    def add_edge(case_id, source, target, relation, attributes, evidence):
        nonlocal edge_count
        edge_count += 1
        edges.append({
            "edge_id": f"edge_{edge_count:06d}",
            "case_id": case_id,
            "source_id": source,
            "target_id": target,
            "relation": relation,
            "attributes": attributes,
            "evidence": evidence,
        })

    for case in cases:
        case_id = case["case_id"]
        case_node_id = f"case:{case_id}"
        nodes.append({
            "node_id": case_node_id,
            "case_id": case_id,
            "type": "Case",
            "label": case_id,
            "mention_text": "",
            "sentence_id": "",
            "start": "",
            "end": "",
            "attributes": {
                "article_id": case.get("article_id", ""),
                "age": case.get("age", ""),
                "gender": case.get("gender", ""),
                "title": case.get("title", ""),
            },
            "evidence": "",
        })

        extracted = extract_case(case, lexicon, triggers)
        by_sentence = defaultdict(list)
        for item in extracted:
            by_sentence[item["sentence_id"]].append(item)

        previous_event = None
        previous_event_sentence_id = None
        treatment_edges = set()
        for sentence_id in sorted(by_sentence):
            items = by_sentence[sentence_id]
            entities = _deduplicate_aliases([
                item for item in items if item["match_kind"] == "entity"
            ])
            sentence_triggers = [item for item in items if item["match_kind"] == "trigger"]
            patterns = [item for item in items if item["match_kind"] == "pattern"]
            created = []

            for entity in entities:
                negation = _scope_trigger(
                    entity,
                    sentence_triggers,
                    "negation",
                    allow_after=entity["match_type"] in {"Symptom", "Condition"},
                )
                resolution = None
                if entity["match_type"] in {"Symptom", "Condition"}:
                    resolution = _scope_trigger(
                        entity, sentence_triggers, "resolution", allow_after=True
                    )
                not_performed = None
                if entity["match_type"] in {"Exam", "Treatment"}:
                    not_performed = _scope_trigger(
                        entity, sentence_triggers, "not_performed", allow_after=True
                    )
                if negation or resolution or not_performed or _mentions_other_person(entity):
                    # Não transforma negação, resolução, plano recusado ou
                    # condição de outra pessoa em fato do paciente.
                    continue

                uncertainty = _scope_trigger(
                    entity, sentence_triggers, "uncertainty", allow_after=True
                )
                compatible = [
                    trigger for trigger in sentence_triggers
                    if _compatible_relation(entity["match_type"], trigger)
                ]
                relation_trigger = _nearest(entity, compatible, max_distance=150)

                attributes = {
                    "assertion": "suspected" if uncertainty else "affirmed",
                    "source": entity["attributes"].get("source", ""),
                }

                if entity["match_type"] == "Treatment":
                    dose = _nearby_pattern(entity, patterns, "dose")
                    if dose:
                        attributes["dose"] = dose["match_text"]

                if entity["match_type"] == "Exam":
                    if entity["normalized_value"] == "laboratory testing":
                        measurements = [
                            p["match_text"] for p in patterns
                            if p["match_type"] == "measurement"
                        ]
                        if measurements:
                            attributes["measurements"] = measurements

                times = _entity_times(entity, patterns, sentence_triggers)
                if times:
                    attributes["time"] = times

                node_count += 1
                node_id = f"event:{case_id}:{node_count:06d}"
                node = {
                    "node_id": node_id,
                    "case_id": case_id,
                    "type": entity["match_type"],
                    "label": entity["normalized_value"],
                    "mention_text": entity["match_text"],
                    "sentence_id": sentence_id,
                    "start": entity["start"],
                    "end": entity["end"],
                    "attributes": attributes,
                    "evidence": entity["sentence_text"],
                }
                nodes.append(node)
                created.append(node)

                edge_attributes = {
                    "assertion": attributes["assertion"],
                    "method": "trigger+lexicon" if relation_trigger else "lexicon",
                }
                if relation_trigger:
                    edge_attributes["trigger"] = relation_trigger["match_text"]
                add_edge(
                    case_id,
                    case_node_id,
                    node_id,
                    CASE_RELATIONS[entity["match_type"]],
                    edge_attributes,
                    entity["sentence_text"],
                )

            # "X days later" conecta apenas um evento narrativo imediatamente
            # anterior a uma entidade que aparece depois da expressão temporal.
            relative_times = [
                p for p in patterns
                if p["match_type"] == "relative_time"
                and _is_forward_time(p["match_text"])
                and _local_start(p) <= 60
            ]
            if (
                previous_event
                and created
                and relative_times
                and sentence_id - previous_event_sentence_id <= 2
            ):
                for relative_time in relative_times:
                    timed_nodes = [
                        node for node in created
                        if relative_time["end"] <= node["start"]
                        and relative_time["match_text"]
                        in node["attributes"].get("time", [])
                    ]
                    if not timed_nodes:
                        continue
                    target = timed_nodes[0]
                    if previous_event["label"] == target["label"]:
                        continue
                    add_edge(
                        case_id,
                        previous_event["node_id"],
                        target["node_id"],
                        "BEFORE",
                        {
                            "time_expression": relative_time["match_text"],
                            "method": "explicit_relative_time",
                        },
                        target["evidence"],
                    )
                    break

            # Exame + gatilho de resultado + condição na mesma frase.
            indication_triggers = [
                t for t in sentence_triggers
                if t["match_type"] == "relation"
                and t["normalized_value"] == "INDICATES"
            ]
            exams = [node for node in created if node["type"] == "Exam"]
            conditions = [node for node in created if node["type"] == "Condition"]
            indication_edges = set()
            for trigger in indication_triggers:
                exam, condition = _bridged_pair(trigger, exams, conditions)
                if not exam or not condition:
                    continue
                pair = (exam["node_id"], condition["node_id"])
                if pair in indication_edges:
                    continue
                indication_edges.add(pair)
                add_edge(
                    case_id,
                    exam["node_id"],
                    condition["node_id"],
                    "INDICATES",
                    {"trigger": trigger["match_text"]},
                    trigger["sentence_text"],
                )

            # Tratamento + condição só gera TREATS com evidência explícita.
            treatments = [node for node in created if node["type"] == "Treatment"]
            target_triggers = [
                trigger for trigger in sentence_triggers
                if trigger["match_type"] == "treatment_target"
            ]
            direct_treatment_triggers = [
                trigger for trigger in sentence_triggers
                if trigger["match_type"] == "relation"
                and trigger["normalized_value"] == "RECEIVED_TREATMENT"
                and trigger["match_text"].lower() in {
                    "treated with", "treatment with", "managed with"
                }
            ]

            for trigger in target_triggers:
                nearby_treatments = _near_nodes(trigger, treatments)
                nearby_conditions = _near_nodes(trigger, conditions)
                for treatment in nearby_treatments:
                    for condition in nearby_conditions:
                        pair = (treatment["node_id"], condition["node_id"])
                        if pair in treatment_edges:
                            continue
                        treatment_edges.add(pair)
                        add_edge(
                            case_id,
                            treatment["node_id"],
                            condition["node_id"],
                            "TREATS",
                            {
                                "trigger": trigger["match_text"],
                                "method": "explicit_treatment_target",
                                "condition_assertion": condition["attributes"]["assertion"],
                            },
                            trigger["sentence_text"],
                        )

            for trigger in direct_treatment_triggers:
                treatment = _nearest(trigger, treatments, max_distance=180)
                condition = _nearest(trigger, conditions, max_distance=180)
                if not treatment or not condition:
                    continue
                pair = (treatment["node_id"], condition["node_id"])
                if pair in treatment_edges:
                    continue
                treatment_edges.add(pair)
                add_edge(
                    case_id,
                    treatment["node_id"],
                    condition["node_id"],
                    "TREATS",
                    {
                        "trigger": trigger["match_text"],
                        "method": "explicit_treatment_relation",
                        "condition_assertion": condition["attributes"]["assertion"],
                    },
                    trigger["sentence_text"],
                )

            if created:
                previous_event = created[-1]
                previous_event_sentence_id = sentence_id

    return nodes, edges


def write_records(path, records, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["attributes"] = _json(row["attributes"])
            writer.writerow(row)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Gera nodes.csv e edges.csv.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    parser.add_argument("--triggers", type=Path, default=TRIGGERS_PATH)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cases = read_csv(args.input)
    lexicon = prepare_entries(read_csv(args.lexicon), "term")
    triggers = prepare_entries(read_csv(args.triggers), "phrase")
    nodes, edges = build_graph(cases, lexicon, triggers)
    write_records(args.nodes, nodes, NODE_FIELDS)
    write_records(args.edges, edges, EDGE_FIELDS)
    print(f"Casos processados: {len(cases)}")
    print(f"Nós gerados: {len(nodes)}")
    print(f"Arestas geradas: {len(edges)}")
    print(f"Nós: {args.nodes}")
    print(f"Arestas: {args.edges}")


if __name__ == "__main__":
    main()
