import yaml
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from manager.forms import ConfigForm


CONFIG_PATH = settings.BASE_DIR / ".config" / "config.yaml"


def _read_config_file():
    raw_yaml = CONFIG_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_yaml) or {}
    if not isinstance(data, dict):
        data = {}
    return data, raw_yaml


def _write_config_file(data):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    CONFIG_PATH.write_text(rendered, encoding="utf-8")


@staff_member_required
def config_manager(request):
    config_data, raw_yaml = _read_config_file()

    if request.method == "POST":
        form = ConfigForm(request.POST, config_data=config_data, raw_yaml=raw_yaml)
        if form.is_valid():
            _write_config_file(form.to_config())
            messages.success(request, "Đã lưu .config/config.yaml.")
            return redirect("manager-config")
    else:
        form = ConfigForm(config_data=config_data, raw_yaml=raw_yaml)

    return render(
        request,
        "manager/config.html",
        {
            "form": form,
            "config_path": CONFIG_PATH,
        },
    )
