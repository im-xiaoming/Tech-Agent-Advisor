import yaml
from django import forms


CONFIG_FIELDS = {
    # chunking
    "chunk_size":                    ("chunking",  "chunk_size"),
    "chunk_overlap":                 ("chunking",  "chunk_overlap"),
    # retriever
    "score_threshold":               ("retriever", "score_threshold"),
    "hybrid_enabled":                ("retriever", "hybrid_enabled"),
    "sparse_model":                  ("retriever", "sparse_model"),
    "self_query_enabled":            ("retriever", "self_query_enabled"),
    # reranker
    "reranker_enabled":              ("reranker",  "enabled"),
    "reranker_model":                ("reranker",  "model"),
    "reranker_top_n":                ("reranker",  "top_n"),
    "reranker_candidate_multiplier": ("reranker",  "candidate_multiplier"),
    "reranker_hallucination_threshold": ("reranker", "hallucination_threshold"),
    "reranker_min_rerank_score":     ("reranker",  "min_rerank_score"),
    "reranker_regenerate_enabled":   ("reranker",  "regenerate_enabled"),
    "reranker_regenerate_threshold": ("reranker",  "regenerate_threshold"),
    "reranker_max_regenerations":    ("reranker",  "max_regenerations"),
    # chat_history
    "num_chats_retained":            ("chat_history", "num_chats_retained"),
    "max_length":                    ("chat_history", "max_length"),
    "beam_size":                     ("chat_history", "beam_size"),
    # splitter
    "splitter_method":               ("splitter",  "method"),
    # embedding
    "embedding_provider":            ("embedding", "embedding_provider"),
    "embedding_model":               ("embedding", "embedding_model"),
    "embedding_dimension":           ("embedding", "dimension"),
    "embedding_device":              ("embedding", "device"),
    "embedding_batch_size":          ("embedding", "batch_size"),
    "embedding_max_seq_length":      ("embedding", "max_seq_length"),
    "embedding_ingest_batch_size":   ("embedding", "ingest_batch_size"),
    # loader
    "loader_type":                   ("loader",    "type"),
}

_BOOL_FIELDS = {
    "hybrid_enabled",
    "self_query_enabled",
    "reranker_enabled",
    "reranker_regenerate_enabled",
}


class ConfigForm(forms.Form):
    # --- Chunking ---
    chunk_size = forms.IntegerField(min_value=1, label="Chunk size")
    chunk_overlap = forms.IntegerField(min_value=0, label="Chunk overlap")

    # --- Retriever ---
    score_threshold = forms.FloatField(min_value=0, max_value=1, label="Score threshold")
    hybrid_enabled = forms.BooleanField(required=False, label="Hybrid search (dense + BM25)")
    sparse_model = forms.CharField(required=False, label="Sparse model")
    self_query_enabled = forms.BooleanField(required=False, label="Self-query filter")

    # --- Reranker ---
    reranker_enabled = forms.BooleanField(required=False, label="Reranker enabled")
    reranker_model = forms.CharField(required=False, label="Reranker model")
    reranker_top_n = forms.IntegerField(min_value=1, label="Top N")
    reranker_candidate_multiplier = forms.IntegerField(min_value=1, label="Candidate multiplier")
    reranker_hallucination_threshold = forms.FloatField(min_value=0, max_value=1, label="Hallucination threshold")
    reranker_min_rerank_score = forms.FloatField(min_value=0, max_value=1, label="Min rerank score")
    reranker_regenerate_enabled = forms.BooleanField(required=False, label="Regenerate enabled")
    reranker_regenerate_threshold = forms.FloatField(min_value=0, max_value=1, label="Regenerate threshold")
    reranker_max_regenerations = forms.IntegerField(min_value=0, label="Max regenerations")

    # --- Chat history ---
    num_chats_retained = forms.IntegerField(min_value=0, label="Chats retained")
    max_length = forms.IntegerField(min_value=1, label="Max history length")
    beam_size = forms.IntegerField(min_value=1, label="Beam size")

    # --- Splitter ---
    splitter_method = forms.CharField(label="Splitter method")

    # --- Embedding ---
    embedding_provider = forms.CharField(label="Embedding provider")
    embedding_model = forms.CharField(label="Embedding model")
    embedding_dimension = forms.IntegerField(min_value=1, label="Embedding dimension")
    embedding_device = forms.CharField(required=False, label="Device (auto / cuda / cpu)")
    embedding_batch_size = forms.IntegerField(min_value=1, label="Batch size")
    embedding_max_seq_length = forms.IntegerField(min_value=1, label="Max seq length")
    embedding_ingest_batch_size = forms.IntegerField(min_value=1, label="Ingest batch size")

    # --- Loader ---
    loader_type = forms.CharField(label="Loader type")

    # --- Raw YAML ---
    raw_yaml = forms.CharField(
        label="Raw YAML",
        required=True,
        widget=forms.Textarea(attrs={"rows": 22, "spellcheck": "false"}),
    )

    def __init__(self, *args, config_data=None, raw_yaml="", **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "manager-checkbox")
            else:
                field.widget.attrs.setdefault("class", "manager-input")

        self.fields["raw_yaml"].widget.attrs["class"] = "manager-input manager-yaml"

        if config_data and not self.is_bound:
            self.initial.update(self._initial_from_config(config_data))
            self.initial["raw_yaml"] = raw_yaml

    def clean_raw_yaml(self):
        raw_yaml = self.cleaned_data["raw_yaml"]
        try:
            parsed = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise forms.ValidationError(f"YAML không hợp lệ: {exc}") from exc

        if not isinstance(parsed, dict):
            raise forms.ValidationError("YAML gốc phải là một object/map.")

        self.cleaned_data["parsed_yaml"] = parsed
        return raw_yaml

    def to_config(self):
        config = self.cleaned_data.get("parsed_yaml", {}).copy()

        for field_name, (section, key) in CONFIG_FIELDS.items():
            value = self.cleaned_data.get(field_name)
            if field_name in _BOOL_FIELDS:
                value = bool(value)
            if value is None and field_name not in _BOOL_FIELDS:
                continue
            config.setdefault(section, {})
            config[section][key] = value

        return config

    @staticmethod
    def _initial_from_config(config):
        initial = {}
        for field_name, (section, key) in CONFIG_FIELDS.items():
            initial[field_name] = config.get(section, {}).get(key)
        return initial
