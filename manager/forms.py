import yaml
from django import forms


CONFIG_FIELDS = {
    "chunk_size": ("chunking", "chunk_size"),
    "chunk_overlap": ("chunking", "chunk_overlap"),
    "score_threshold": ("retriever", "score_threshold"),
    "num_chats_retained": ("chat_history", "num_chats_retained"),
    "max_length": ("chat_history", "max_length"),
    "beam_size": ("chat_history", "beam_size"),
    "splitter_method": ("splitter", "method"),
    "embedding_provider": ("embedding", "embedding_provider"),
    "embedding_model": ("embedding", "embedding_model"),
    "embedding_dimension": ("embedding", "dimension"),
    "loader_type": ("loader", "type"),
}


class ConfigForm(forms.Form):
    chunk_size = forms.IntegerField(min_value=1, label="Chunk size")
    chunk_overlap = forms.IntegerField(min_value=0, label="Chunk overlap")
    score_threshold = forms.FloatField(min_value=0, max_value=1, label="Score threshold")
    num_chats_retained = forms.IntegerField(min_value=0, label="Chats retained")
    max_length = forms.IntegerField(min_value=1, label="Max history length")
    beam_size = forms.IntegerField(min_value=1, label="Beam size")
    splitter_method = forms.CharField(label="Splitter method")
    embedding_provider = forms.CharField(label="Embedding provider")
    embedding_model = forms.CharField(label="Embedding model")
    embedding_dimension = forms.IntegerField(min_value=1, label="Embedding dimension")
    loader_type = forms.CharField(label="Loader type")
    raw_yaml = forms.CharField(
        label="Raw YAML",
        required=True,
        widget=forms.Textarea(attrs={"rows": 18, "spellcheck": "false"}),
    )

    def __init__(self, *args, config_data=None, raw_yaml="", **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
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

        for field_name, path in CONFIG_FIELDS.items():
            section, key = path
            config.setdefault(section, {})
            config[section][key] = self.cleaned_data[field_name]

        return config

    @staticmethod
    def _initial_from_config(config):
        initial = {}
        for field_name, path in CONFIG_FIELDS.items():
            section, key = path
            initial[field_name] = config.get(section, {}).get(key)
        return initial
