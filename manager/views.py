import json
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
DATA_DIR = settings.BASE_DIR / "data"

_CATEGORY_LABELS = {
    "camera": "Camera",
    "charger": "Sạc",
    "desktop": "Máy tính để bàn",
    "ebook": "Đọc sách",
    "fan": "Quạt",
    "hard_drive": "Ổ cứng",
    "headphones": "Tai nghe",
    "hub": "Hub",
    "keyboard": "Bàn phím",
    "laptop": "Laptop",
    "memory_card": "Thẻ nhớ",
    "microphone": "Micro",
    "mobile": "Điện thoại",
    "monitor": "Màn hình",
    "mouse": "Chuột",
    "network": "Thiết bị mạng",
    "powerbank": "Pin dự phòng",
    "printer": "Máy in",
    "projector": "Máy chiếu",
    "smartwatch": "Đồng hồ thông minh",
    "smart_light": "Đèn thông minh",
    "speaker": "Loa",
    "tablet": "Máy tính bảng",
    "usb": "USB",
    "watch": "Đồng hồ",
}


def _category_from_filename(path):
    stem = path.stem  # e.g. "tgdd_laptop" or "cellphones_mobile"
    for key, label in _CATEGORY_LABELS.items():
        if stem.endswith(key):
            return key, label
    return stem, stem


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


def _load_product_records():
    """Load all JSONL files from the data directory."""
    records = []
    if not DATA_DIR.exists():
        return records

    for jsonl_file in sorted(DATA_DIR.glob("*.jsonl")):
        cat_key, cat_label = _category_from_filename(jsonl_file)
        with jsonl_file.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                item["line_number_display"] = line_number
                item["category_key"] = cat_key
                item["category_label"] = cat_label
                item["source_file"] = jsonl_file.name
                records.append(item)
    return records


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
def product_data_view(request):
    """Admin-only page for browsing all product data from JSONL files."""
    all_records = _load_product_records()

    search = request.GET.get("q", "").strip()
    brand = request.GET.get("brand", "").strip()
    category = request.GET.get("category", "").strip()

    records = all_records

    if category:
        records = [r for r in records if r.get("category_key") == category]

    if search:
        needle = search.casefold()
        records = [
            item for item in records
            if needle in " ".join(
                str(item.get(key, ""))
                for key in ("title", "brand", "description", "specs", "text", "url")
            ).casefold()
        ]

    if brand:
        records = [
            item for item in records
            if str(item.get("brand", "")).strip().casefold() == brand.casefold()
        ]

    brands = sorted(
        {str(r.get("brand", "")).strip() for r in records if str(r.get("brand", "")).strip()},
        key=str.casefold,
    )

    categories = sorted(
        {(r["category_key"], r["category_label"]) for r in all_records},
        key=lambda x: x[1].casefold(),
    )

    paginator = Paginator(records, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "manager/product_data.html",
        {
            "page_obj": page,
            "brands": brands,
            "categories": categories,
            "current_search": search,
            "current_brand": brand,
            "current_category": category,
            "data_path": DATA_DIR,
            "total_records": len(all_records),
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
