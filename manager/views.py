import yaml
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from manager.forms import ConfigForm
from manager.models import ChatLog


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


@staff_member_required
def log_list(request):
    """Paginated list of ChatLog entries with filters."""
    queryset = ChatLog.objects.select_related("user").all()

    flag = request.GET.get("flag", "").strip()
    if flag:
        queryset = queryset.filter(hallucination_flag=flag)

    search = request.GET.get("q", "").strip()
    if search:
        queryset = queryset.filter(Q(query__icontains=search) | Q(answer__icontains=search))

    username = request.GET.get("user", "").strip()
    if username:
        queryset = queryset.filter(user__username__icontains=username)

    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "manager/log_list.html",
        {
            "page_obj": page,
            "flag_choices": ChatLog.FLAG_CHOICES,
            "current_flag": flag,
            "current_search": search,
            "current_user": username,
        },
    )


@staff_member_required
def log_detail(request, log_id):
    log = get_object_or_404(ChatLog.objects.select_related("user"), pk=log_id)
    return render(
        request,
        "manager/log_detail.html",
        {
            "log": log,
            "flag_choices": ChatLog.FLAG_CHOICES,
        },
    )


@staff_member_required
@require_POST
def log_flag(request, log_id):
    log = get_object_or_404(ChatLog, pk=log_id)
    flag = request.POST.get("flag", "").strip()
    note = request.POST.get("note", "").strip()
    valid_flags = {choice for choice, _ in ChatLog.FLAG_CHOICES}
    if flag in valid_flags:
        log.hallucination_flag = flag
    if note:
        log.reviewer_note = note
    log.save(update_fields=["hallucination_flag", "reviewer_note"])
    messages.success(request, f"Đã cập nhật log #{log.pk}.")
    return redirect("manager-log-detail", log_id=log.pk)
