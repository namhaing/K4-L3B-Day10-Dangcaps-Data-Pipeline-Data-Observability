"""Dashboard demo theo checkpoint (bonus B1). Chạy: streamlit run script/demo_dashboard.py"""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from core.config import load_settings
from core.utils import read_json
from evaluation.metrics import _token_f1
from ingestion.crossref import fetch_source_records
from observability.quality import run_data_quality_checks
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

STATES = ["baseline", "corrupted", "repaired"]
STATE_LABELS = {"baseline": "Sạch (Baseline)", "corrupted": "Bẩn (Corrupted)", "repaired": "Đã sửa (Repaired)"}
# Categorical slots 1-3 of the reference palette (validated all-pairs for CVD).
STATE_COLORS = {"baseline": "#2a78d6", "corrupted": "#eb6834", "repaired": "#1baf7a"}
RATE_METRICS = {
    "retrieval_hit_rate": "Tìm đúng tài liệu (hit rate)",
    "mean_token_f1": "Độ khớp từ (token F1)",
    "judge_accuracy": "Trả lời đúng (judge)",
}
JUDGE_SCORE_LABEL = "Điểm judge TB (1–5)"
QUESTION_TYPES_VI = {"summary": "Tóm tắt", "authors": "Tác giả", "date": "Ngày xuất bản", "categories": "Chủ đề"}
# kind -> (icon, tên lỗi, giống sự cố nào ngoài đời, cách tạo)
CORRUPTIONS_VI = {
    "drop_latest": ("🗑️", "Mất các bài mới nhất", "Job tải dữ liệu chết giữa chừng", "Xóa 20% số bài có ngày xuất bản mới nhất"),
    "blank_summary": ("⬜", "Xóa trắng phần tóm tắt", "API trả về trường rỗng", "Thay phần tóm tắt bằng chuỗi rỗng"),
    "inject_noise": ("🌀", "Chèn ký tự rác vào tóm tắt", "Lỗi encoding, dữ liệu bẩn", "Chèn ký tự rác vào đầu tóm tắt và sau mỗi 4 từ"),
    "truncate_title": ("✂️", "Tên bài bị cắt còn 6 ký tự", "Cột database bị giới hạn độ dài", "Cắt tên bài còn 6 ký tự (dưới mức tối thiểu 8)"),
    "stale_date": ("📅", "Ngày xuất bản bị lùi 400 ngày", "Lấy nhầm bản dữ liệu cũ", "Lùi ngày xuất bản 400 ngày rồi tính lại age_days"),
    "duplicate_rows": ("👯", "Nhân bản dòng dữ liệu", "Job chạy lặp 2 lần", "Nhân bản nguyên dòng dữ liệu"),
}
CHECKS_VI = {
    ("table_row_count_to_be_between", ""): "Số lượng bài hợp lý (21–24 bài)",
    ("column_values_to_not_be_null", "paper_id"): "Không bài nào thiếu mã bài",
    ("column_values_to_not_be_null", "title"): "Không bài nào thiếu tên",
    ("column_values_to_not_be_null", "summary"): "Không bài nào thiếu tóm tắt",
    ("column_values_to_not_be_null", "published"): "Không bài nào thiếu ngày xuất bản",
    ("column_values_to_be_unique", "paper_id"): "Không có bài bị trùng lặp",
    ("column_value_lengths_to_be_between", "title"): "Tên bài dài ít nhất 8 ký tự",
    ("column_value_lengths_to_be_between", "summary"): "Tóm tắt dài ít nhất 50 ký tự",
}


def corruption_name(kind: str) -> str:
    return CORRUPTIONS_VI.get(kind, ("", kind))[1]
INK_SECONDARY = "#52514e"

st.set_page_config(page_title="Day 10 · Data Observability Demo", page_icon="📊", layout="wide")
settings = load_settings()
paths = settings.paths
ROOT = paths.project_dir

METRICS = {"baseline": paths.baseline_metrics, "corrupted": paths.corrupted_metrics, "repaired": paths.repaired_metrics}
ANSWERS = {"baseline": paths.baseline_answers, "corrupted": paths.corrupted_answers, "repaired": paths.repaired_answers}
CLEAN = {"baseline": paths.clean_json, "corrupted": paths.corrupted_clean_json, "repaired": paths.repaired_clean_json}
EMBEDDINGS = {
    "baseline": paths.embeddings_json,
    "corrupted": paths.corrupted_embeddings_json,
    "repaired": paths.repaired_embeddings_json,
}
QUALITY = {state: paths.quality_dir / f"{state}_quality_report.json" for state in STATES}
SELF_HEALING_LOG = paths.corruption_log.parent / "self_healing_log.json"


def load(path: Path) -> Any | None:
    return read_json(path) if Path(path).exists() else None


def load_df(path: Path) -> pd.DataFrame | None:
    if not Path(path).exists():
        return None
    return pd.read_json(path, orient="records", dtype=False, convert_dates=False)


@st.cache_resource(show_spinner="Đang nạp ChromaDB index...")
def get_index(state: str) -> LocalEmbeddingIndex:
    return LocalEmbeddingIndex.load(settings, EMBEDDINGS[state])


def ok(flag: bool) -> str:
    return "✅" if flag else "❌"


def run_script(name: str) -> None:
    """Chạy script pipeline thật và stream log ra màn hình."""
    env = {**os.environ, "PYTHONUTF8": "1"}
    placeholder = st.empty()
    lines: list[str] = []
    with st.spinner(f"Đang chạy {name}..."):
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "script" / name)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in process.stdout:
            line = line.rstrip()
            if not line or "Calculating Metrics" in line or "Loading weights" in line or "Warning" in line:
                continue
            lines.append(line)
            placeholder.code("\n".join(lines[-30:]), language="text")
        code = process.wait()
    st.cache_resource.clear()
    if code == 0:
        st.success(f"{name}: exit code 0")
    else:
        st.error(f"{name}: exit code {code}")


def metric_frame() -> pd.DataFrame:
    rows = []
    for state in STATES:
        metrics = load(METRICS[state])
        if not metrics:
            continue
        for key, label in RATE_METRICS.items():
            rows.append({"state": state, "Trạng thái": STATE_LABELS[state], "metric": label, "value": metrics[key]})
    return pd.DataFrame(rows)


def comparison_chart(df: pd.DataFrame) -> alt.FacetChart:
    base = alt.Chart().encode(
        x=alt.X("state:N", sort=STATES, axis=None),
        y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 1.1]), title=None, axis=alt.Axis(grid=True, gridOpacity=0.3)),
    )
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=34).encode(
        color=alt.Color(
            "state:N",
            scale=alt.Scale(domain=STATES, range=[STATE_COLORS[s] for s in STATES]),
            legend=alt.Legend(title=None, orient="top", labelExpr=" : ".join(f"datum.label == '{k}' ? '{v}'" for k, v in STATE_LABELS.items()) + " : datum.label"),
        ),
        tooltip=[alt.Tooltip("Trạng thái:N"), alt.Tooltip("metric:N", title="Chỉ số"), alt.Tooltip("value:Q", format=".3f", title="Giá trị")],
    )
    labels = base.mark_text(dy=-8, color=INK_SECONDARY, fontSize=12).encode(text=alt.Text("value:Q", format=".2f"))
    return alt.layer(bars, labels, data=df).properties(width=170, height=240).facet(
        column=alt.Column("metric:N", sort=list(RATE_METRICS.values()), title=None, header=alt.Header(labelFontSize=13))
    )


def age_histogram(df: pd.DataFrame, state: str) -> alt.LayerChart:
    threshold = settings.freshness_threshold_days
    upper = max(int(df["age_days"].max()) + 30, threshold + 60)
    bars = (
        alt.Chart(df)
        .mark_bar(color=STATE_COLORS[state], cornerRadiusTopLeft=4, cornerRadiusTopRight=4, binSpacing=2)
        .encode(
            x=alt.X("age_days:Q", bin=alt.Bin(step=30, extent=[0, upper]), title="Tuổi bài báo (số ngày kể từ khi xuất bản)"),
            y=alt.Y("count():Q", title="Số bài"),
            tooltip=[alt.Tooltip("count():Q", title="Số bài")],
        )
    )
    rule_df = pd.DataFrame({"x": [threshold], "label": [f"Ngưỡng {threshold} ngày"]})
    rule = alt.Chart(rule_df).mark_rule(color=INK_SECONDARY, strokeDash=[4, 4], strokeWidth=2).encode(x="x:Q")
    text = alt.Chart(rule_df).mark_text(align="left", dx=6, dy=-6, color=INK_SECONDARY, baseline="top").encode(
        x="x:Q", y=alt.value(0), text="label:N"
    )
    return alt.layer(bars, rule, text).properties(height=260)


def expectation_table(states: list[str]) -> pd.DataFrame | None:
    reports = {state: load(QUALITY[state]) for state in states}
    if not any(reports.values()):
        return None
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for state, report in reports.items():
        for item in (report or {}).get("expectations", []):
            key = (item["expectation"].replace("expect_", ""), item.get("column") or "")
            label = CHECKS_VI.get(key, key[0])
            rows.setdefault(key, {"Kiểm tra": label, "Expectation (GX)": key[0]})[STATE_LABELS[state]] = ok(item["success"])
    return pd.DataFrame(rows.values())


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("⚙️ Cấu hình")
    st.markdown(
        f"""
- **LLM:** `{settings.llm_provider}` / `{settings.model_name}`
- **Embedding:** `{settings.embedding_model.split('/')[-1]}`
- **top_k:** {settings.top_k} · **Freshness:** {settings.freshness_threshold_days} ngày, tối đa 25% stale
- **REFRESH_SOURCE:** {'bật (gọi API live)' if settings.refresh_source else 'tắt (đọc snapshot)'}
"""
    )
    st.divider()
    st.header("▶️ Chạy pipeline thật")
    run_phase1 = st.button("Chạy Phase 1 (CP0 → CP3)", width="stretch")
    run_flow = st.button("Chạy Corruption Flow (CP4 → CP5)", width="stretch")
    st.caption("Phase 1 ~1–2 phút, Corruption Flow ~2–3 phút. Kết quả ghi vào `data/`.")

st.title("📊 Day 10 — Data Pipeline & Data Observability cho RAG")
st.caption("Nhóm Dangcaps · Baseline → Corrupted → Repaired · mọi số liệu đọc trực tiếp từ artifact trong `data/`")

if run_phase1:
    run_script("run_phase1.py")
if run_flow:
    run_script("run_corruption_flow.py")

story_tab, *tabs = st.tabs(
    [
        "🎬 Demo 5 bước",
        "🧭 Tổng quan",
        "CP0 · Thu thập dữ liệu",
        "CP1 · Làm sạch & Kiểm định",
        "CP2 · Bộ câu hỏi & Index",
        "CP3 · Kết quả dữ liệu sạch",
        "CP4 · Làm bẩn dữ liệu",
        "CP5 · Tự sửa & So sánh",
        "💬 Hỏi thử RAG",
        "CP6 · Checklist nộp bài",
    ]
)

raw_records = load(paths.raw_records_json) or []
clean_df = load_df(paths.clean_json)
test_set = load(paths.eval_testset) or []
corruption_log = load(paths.corruption_log)
metrics = {state: load(METRICS[state]) for state in STATES}
quality = {state: load(QUALITY[state]) for state in STATES}


# ---------------------------------------------------------------- story (guided demo)
def card(body: str, color: str, height: int | None = None) -> None:
    style = f"min-height:{height}px;" if height else ""
    st.markdown(
        f"<div style='border:1px solid rgba(128,128,128,.28);border-top:5px solid {color};"
        f"border-radius:10px;padding:14px 16px;{style}'>{body}</div>",
        unsafe_allow_html=True,
    )


def big(value: str, label: str) -> str:
    return (
        f"<div style='font-size:2.1rem;font-weight:700;line-height:1.1'>{value}</div>"
        f"<div style='opacity:.75;font-size:.92rem'>{label}</div>"
    )


def count_of(state: str, key: str) -> str:
    m = metrics[state]
    return f"{round(m[key] * m['samples'])}/{m['samples']}"




def check_results(report: dict) -> dict[tuple[str, str], bool]:
    return {
        (item["expectation"].replace("expect_", ""), item.get("column") or ""): item["success"]
        for item in report.get("expectations", [])
    }


with story_tab:
    if not all(metrics.values()) or not corruption_log or not all(quality.values()):
        st.info("Chưa đủ kết quả 3 trạng thái — chạy Phase 1 và Corruption Flow ở thanh bên trước.")
    else:
        bad_checks = check_results(quality["corrupted"])
        fresh_bad = quality["corrupted"]["freshness"]
        st.markdown(
            "### Dữ liệu bẩn làm AI trả lời sai **mà không báo lỗi** → Quality Gate phát hiện → tự sửa → AI đúng lại"
        )

        # Flow strip: the whole story at a glance.
        failed_total = sum(not v for v in bad_checks.values()) + (0 if fresh_bad["is_fresh"] else 1)
        steps = [
            ("①", "Dữ liệu sạch", big(count_of("baseline", "judge_accuracy"), "câu trả lời đúng"), STATE_COLORS["baseline"]),
            ("②", "Làm bẩn 6 kiểu", big(str(len(corruption_log["corruptions"])), "loại lỗi tiêm vào"), STATE_COLORS["corrupted"]),
            ("③", "AI trả lời sai", big(count_of("corrupted", "judge_accuracy"), "câu trả lời đúng"), STATE_COLORS["corrupted"]),
            ("④", "Gate phát hiện", big(f"{failed_total}/9", "kiểm tra báo lỗi"), "#e34948"),
            ("⑤", "Tự sửa xong", big(count_of("repaired", "judge_accuracy"), "câu trả lời đúng"), STATE_COLORS["repaired"]),
        ]
        cols = st.columns(len(steps))
        for col, (num, title, body, color) in zip(cols, steps):
            with col:
                card(f"<div style='font-weight:600;margin-bottom:6px'>{num} {title}</div>{body}", color, 118)
        st.write("")

        # Step 1
        with st.container(border=True):
            st.markdown("#### ① Dữ liệu sạch: AI trả lời tốt")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Bài báo trong kho", len(clean_df) if clean_df is not None else "—")
            c2.metric("Tìm đúng tài liệu", count_of("baseline", "retrieval_hit_rate"))
            c3.metric("Trả lời đúng", count_of("baseline", "judge_accuracy"))
            c4.metric("Quality Gate", "✅ PASS")
            st.caption("🗣️ *\"Hệ thống RAG tìm bài báo liên quan rồi trả lời. Với dữ liệu sạch, cả 10 câu hỏi kiểm tra đều đúng.\"*")

        # Step 2
        with st.container(border=True):
            st.markdown("#### ② Làm bẩn dữ liệu theo 6 sự cố hay gặp ngoài đời")
            caught = {
                "drop_latest": not bad_checks.get(("table_row_count_to_be_between", ""), True),
                "blank_summary": not bad_checks.get(("column_value_lengths_to_be_between", "summary"), True),
                "inject_noise": False,
                "truncate_title": not bad_checks.get(("column_value_lengths_to_be_between", "title"), True),
                "stale_date": not fresh_bad["is_fresh"],
                "duplicate_rows": not bad_checks.get(("column_values_to_be_unique", "paper_id"), True),
            }
            entries = {c["type"]: c for c in corruption_log["corruptions"]}
            for row in (list(CORRUPTIONS_VI)[:3], list(CORRUPTIONS_VI)[3:]):
                cols = st.columns(3)
                for col, kind in zip(cols, row):
                    icon, name, real, _ = CORRUPTIONS_VI[kind]
                    badge = "🛡️ <b>Gate bắt được</b>" if caught[kind] else "👻 <b>Gate KHÔNG bắt được</b>"
                    with col:
                        card(
                            f"<div style='font-size:1.6rem'>{icon}</div><b>{name}</b> · {entries[kind]['count']} bài"
                            f"<div style='opacity:.75;font-size:.9rem;margin:4px 0 8px'>Ngoài đời: {real}</div>{badge}",
                            STATE_COLORS["corrupted"],
                            150,
                        )
                st.write("")
            st.caption("🗣️ *\"Nhóm cố tình làm hỏng dữ liệu theo 6 kiểu sự cố thật. Có 2 kiểu Quality Gate không bắt được — đó là lý do vẫn phải đo chất lượng câu trả lời.\"*")

        # Step 3
        with st.container(border=True):
            st.markdown("#### ③ Hậu quả: AI trả lời sai, nhưng hệ thống **không hề báo lỗi**")
            c1, c2, c3 = st.columns(3)
            hit_drop = round((metrics["corrupted"]["retrieval_hit_rate"] - metrics["baseline"]["retrieval_hit_rate"]) * 10)
            acc_drop = round((metrics["corrupted"]["judge_accuracy"] - metrics["baseline"]["judge_accuracy"]) * 10)
            c1.metric("Tìm đúng tài liệu", count_of("corrupted", "retrieval_hit_rate"), delta=f"{hit_drop} câu")
            c2.metric("Trả lời đúng", count_of("corrupted", "judge_accuracy"), delta=f"{acc_drop} câu")
            c3.metric("Pipeline báo lỗi?", "Không — exit 0")
            st.error("**Silent failure:** code vẫn chạy bình thường, chỉ có câu trả lời là sai. Không có Quality Gate thì không ai biết.")

            answers = {state: {a["id"]: a for a in load(ANSWERS[state]) or []} for state in STATES}
            candidates = [
                qid for qid, a in answers["corrupted"].items()
                if not a["judge"]["correct"] and answers["baseline"][qid]["judge"]["correct"] and answers["repaired"][qid]["judge"]["correct"]
            ]
            candidates.sort(key=lambda qid: (answers["corrupted"][qid]["question_type"] != "date", qid))
            if candidates:
                example = answers["baseline"][candidates[0]]
                st.markdown(f"**Ví dụ thật ({example['id']}):** {example['question']}")
                st.markdown(f"Đáp án đúng: `{example['ground_truth']}`")
                cols = st.columns(3)
                for col, state in zip(cols, STATES):
                    a = answers[state][example["id"]]
                    verdict = "✅ Đúng" if a["judge"]["correct"] else "❌ Sai"
                    with col:
                        card(
                            f"<div style='font-weight:600'>{STATE_LABELS[state]}</div>"
                            f"<div style='margin:8px 0;font-size:1.05rem'>{a['answer'][:160]}</div><b>{verdict}</b>",
                            STATE_COLORS[state],
                            130,
                        )
            st.caption("🗣️ *\"Cùng một câu hỏi: dữ liệu sạch trả lời đúng, dữ liệu bẩn trả lời sai một cách rất tự tin.\"*")

        # Step 4
        with st.container(border=True):
            st.markdown(f"#### ④ Quality Gate phát hiện: {failed_total}/9 kiểm tra báo lỗi → **chặn dữ liệu**")
            rows = [(CHECKS_VI.get(key, key[0]), passed) for key, passed in bad_checks.items()]
            rows.append((f"Dữ liệu còn mới (≤ 25% bài quá 180 ngày) — hiện {fresh_bad['stale_ratio']:.0%} bài cũ", fresh_bad["is_fresh"]))
            rows.sort(key=lambda r: r[1])
            left, right = st.columns(2)
            for i, (label, passed) in enumerate(rows):
                (left if i < (len(rows) + 1) // 2 else right).markdown(f"{'✅' if passed else '❌'} {label}")
            st.caption("🗣️ *\"Great Expectations kiểm tra 8 luật về dữ liệu, cộng thêm luật độ mới. Dữ liệu bẩn trượt 4 luật nên bị chặn trước khi vào AI.\"*")

        # Step 5
        with st.container(border=True):
            st.markdown("#### ⑤ Tự động sửa: dựng lại từ bản gốc → AI đúng trở lại")
            healing = load(SELF_HEALING_LOG) or []
            chips = []
            for step in healing:
                if step["step"] == "quality_gate":
                    chips.append(f"{'✅' if step['success'] else '❌'} Gate {STATE_LABELS[step['state']]}: {'PASS' if step['success'] else 'FAIL'}")
                else:
                    chips.append("🔧 Tự động dựng lại từ dữ liệu gốc")
            st.markdown("  ➜  ".join(f"**{chip}**" for chip in chips))
            c1, c2, c3 = st.columns(3)
            c1.metric("Tìm đúng tài liệu", count_of("repaired", "retrieval_hit_rate"), delta="về như ban đầu", delta_color="off")
            c2.metric("Trả lời đúng", count_of("repaired", "judge_accuracy"), delta="về như ban đầu", delta_color="off")
            c3.metric("Quality Gate", "✅ PASS")
            st.altair_chart(comparison_chart(metric_frame()), width="content")
            st.caption("🗣️ *\"Khi Gate báo lỗi, pipeline tự bỏ dữ liệu bẩn và dựng lại từ bản gốc đã lưu. Chạy bao nhiêu lần cũng ra cùng kết quả.\"*")

        st.success(
            "**3 điều rút ra:** ① Dữ liệu hỏng thì AI sai mà không báo lỗi. "
            "② Quality Gate + kiểm tra độ mới bắt được phần lớn lỗi — nhưng không phải tất cả, nên phải đo cả chất lượng câu trả lời. "
            "③ Luôn giữ bản dữ liệu gốc để phục hồi an toàn."
        )

# ---------------------------------------------------------------- overview
with tabs[0]:
    types = {item["question_type"] for item in test_set}
    log_types = {c["type"] for c in (corruption_log or {}).get("corruptions", [])}
    b, c, r = metrics["baseline"], metrics["corrupted"], metrics["repaired"]
    rows = [
        ("CP0", "Tải đủ 24 bài, lưu 2 file raw", len(raw_records) == 24 and paths.raw_api_response.exists(), f"{len(raw_records)} bài"),
        ("CP1", "Clean 24 dòng + GX success=True", clean_df is not None and len(clean_df) == 24 and bool(quality["baseline"] and quality["baseline"]["success"]), f"{0 if clean_df is None else len(clean_df)} dòng"),
        ("CP2", "Test set 10 câu, 4 loại", len(test_set) == 10 and len(types) == 4, f"{len(test_set)} câu, {len(types)} loại"),
        ("CP3", "baseline_metrics + phase1_report", bool(b) and paths.baseline_report.exists(), f"hit rate {b['retrieval_hit_rate']:.2f}" if b else "chưa chạy"),
        ("CP4", "Đủ 6 lỗi + metrics sụt giảm", len(log_types) == 6 and bool(b and c) and c["retrieval_hit_rate"] < b["retrieval_hit_rate"], f"{len(log_types)} loại lỗi"),
        ("CP5", "Repaired = Baseline + report 3 trạng thái", bool(b and r) and all(abs(r[k] - b[k]) < 1e-9 for k in RATE_METRICS) and paths.comparison_report.exists(), "đã phục hồi" if b and r else "chưa chạy"),
    ]
    st.dataframe(
        pd.DataFrame([{"Checkpoint": cp, "Tín hiệu nghiệm thu": sig, "Trạng thái": ok(flag), "Chi tiết": det} for cp, sig, flag, det in rows]),
        hide_index=True,
        width="stretch",
    )
    frame = metric_frame()
    if len(frame["state"].unique()) == 3 if not frame.empty else False:
        st.subheader("Baseline vs Corrupted vs Repaired")
        st.altair_chart(comparison_chart(frame), width="content")
    else:
        st.info("Chưa đủ 3 trạng thái — bấm **Chạy Phase 1** rồi **Chạy Corruption Flow** ở thanh bên.")

# ---------------------------------------------------------------- CP0
with tabs[1]:
    st.subheader("CP0 · Thu thập dữ liệu gốc & lưu vết (lineage)")
    col1, col2, col3 = st.columns(3)
    col1.metric("Số bài gốc", len(raw_records))
    col2.metric("crossref_response.json", "có" if paths.raw_api_response.exists() else "thiếu")
    col3.metric("Nguồn", "Bản lưu sẵn (snapshot)" if not settings.refresh_source else "Gọi API trực tiếp")
    if st.button("Chạy tín hiệu CP0 (fetch_source_records)"):
        records = fetch_source_records(settings)
        st.success(f"Tín hiệu hoàn thành: Đã tải {len(records)} bài báo")
    if raw_records:
        st.dataframe(
            pd.DataFrame(raw_records)[["paper_id", "title", "published", "primary_category"]].rename(
                columns={"paper_id": "Mã bài (DOI)", "title": "Tên bài", "published": "Ngày xuất bản", "primary_category": "Chủ đề chính"}
            ),
            hide_index=True,
            width="stretch",
        )

# ---------------------------------------------------------------- CP1
with tabs[2]:
    st.subheader("CP1 · Làm sạch dữ liệu & Quality Gate (Great Expectations 1.x + độ mới dữ liệu)")
    if clean_df is None:
        st.info("Chưa có `papers_clean.json` — chạy Phase 1.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Số bài sau làm sạch", len(clean_df))
        col2.metric("Số bài trùng mã", int(clean_df["paper_id"].duplicated().sum()))
        col3.metric("Quality Gate baseline", "PASS" if quality["baseline"] and quality["baseline"]["success"] else "FAIL")
        pick = st.selectbox("Xem `text_for_embedding` của bài", clean_df["title"].tolist())
        st.code(clean_df.loc[clean_df["title"] == pick, "text_for_embedding"].iloc[0], language="text")

        if st.button("Chạy lại Quality Gate trực tiếp (GX 1.x, ghi ra thư mục tạm)"):
            with TemporaryDirectory() as temp:
                temp_paths = replace(paths, quality_dir=Path(temp), gx_dir=Path(temp) / "gx")
                result = run_data_quality_checks(clean_df, replace(settings, paths=temp_paths), "demo")
            st.success(f"Tín hiệu hoàn thành: Quality check status = {result['success']}")

        st.markdown("**Kết quả từng expectation**")
        table = expectation_table(STATES)
        if table is not None:
            st.dataframe(table, hide_index=True, width="stretch")

        st.markdown("**Freshness: phân bố `age_days`**")
        state = st.radio("Tập dữ liệu", STATES, format_func=STATE_LABELS.get, horizontal=True, key="age_state")
        df_state = load_df(CLEAN[state])
        if df_state is not None:
            fresh = (quality[state] or {}).get("freshness", {})
            c1, c2, c3 = st.columns(3)
            c1.metric("Tỷ lệ bài cũ (>180 ngày)", f"{fresh.get('stale_ratio', 0):.1%}", help="Ngưỡng tối đa 25%")
            c2.metric("Bài cũ / tổng", f"{fresh.get('stale_rows', '—')} / {fresh.get('total_rows', '—')}")
            c3.metric("Độ mới dữ liệu", "✅ Còn mới" if fresh.get("is_fresh") else "❌ Đã cũ")
            st.altair_chart(age_histogram(df_state, state), width="stretch")

# ---------------------------------------------------------------- CP2
with tabs[3]:
    st.subheader("CP2 · Bộ câu hỏi đánh giá & kho vector ChromaDB")
    if test_set:
        counts = pd.Series([item["question_type"] for item in test_set]).value_counts()
        cols = st.columns(len(counts) + 1)
        cols[0].metric("Tổng số câu", len(test_set))
        for col, (qtype, count) in zip(cols[1:], counts.items()):
            col.metric(QUESTION_TYPES_VI.get(qtype, qtype), int(count))
        st.dataframe(
            pd.DataFrame(
                [
                    {"Câu": i["id"], "Loại": QUESTION_TYPES_VI.get(i["question_type"], i["question_type"]),
                     "Câu hỏi (tiếng Anh)": i["question"], "Đáp án chuẩn": i["ground_truth"]}
                    for i in test_set
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Chưa có `test_set.json` — chạy Phase 1.")
    st.markdown("**ChromaDB collections**")
    cols = st.columns(3)
    for col, state in zip(cols, STATES):
        if EMBEDDINGS[state].exists():
            index = get_index(state)
            col.metric(index.collection_name, f"{index.collection.count()} vector")
        else:
            col.metric(f"papers-{state}", "chưa tạo")

# ---------------------------------------------------------------- CP3
with tabs[4]:
    st.subheader("CP3 · Kết quả trên dữ liệu sạch (baseline)")
    if metrics["baseline"]:
        cols = st.columns(4)
        for col, key in zip(cols, [*RATE_METRICS, "mean_judge_score"]):
            col.metric(RATE_METRICS.get(key, JUDGE_SCORE_LABEL), f"{metrics['baseline'][key]:.3f}")
    if paths.baseline_report.exists():
        with st.container(border=True):
            st.markdown(paths.baseline_report.read_text(encoding="utf-8"))
    else:
        st.info("Chưa có `phase1_report.md` — chạy Phase 1.")

# ---------------------------------------------------------------- CP4
with tabs[5]:
    st.subheader("CP4 · Cố tình làm bẩn dữ liệu & lỗi âm thầm (silent failure)")
    if not corruption_log or not metrics["corrupted"]:
        st.info("Chưa có kết quả corruption — chạy Corruption Flow.")
    else:
        cols = st.columns(4)
        for col, key in zip(cols, [*RATE_METRICS, "mean_judge_score"]):
            value, base = metrics["corrupted"][key], metrics["baseline"][key]
            col.metric(RATE_METRICS.get(key, JUDGE_SCORE_LABEL), f"{value:.3f}", delta=f"{value - base:+.3f}")
        st.caption(f"Trước khi làm bẩn {corruption_log['input_rows']} bài → sau khi làm bẩn {corruption_log['output_rows']} dòng · seed {corruption_log['seed']} (chạy lại luôn ra cùng kết quả)")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Loại lỗi": f"{CORRUPTIONS_VI.get(c['type'], ('', c['type']))[0]} {corruption_name(c['type'])}",
                     "Mã": c["type"], "Số bài": c["count"],
                     "Cách tạo": CORRUPTIONS_VI.get(c["type"], ("", "", "", c["description"]))[3],
                     "Ngoài đời giống": CORRUPTIONS_VI.get(c["type"], ("", "", "—"))[2]}
                    for c in corruption_log["corruptions"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )

        st.markdown("**Ảnh hưởng tới từng câu hỏi** (đối chiếu `corruption_log.json` với `corrupted_answers.json`)")
        affected: dict[str, list[str]] = {}
        for item in corruption_log["corruptions"]:
            for paper_id in item["affected_paper_ids"]:
                affected.setdefault(paper_id, []).append(corruption_name(item["type"]))
        rows = []
        for answer in load(ANSWERS["corrupted"]) or []:
            paper_id = answer["ground_truth_doc_ids"][0]
            silent = answer["token_f1"] >= 0.95 and not answer["retrieval_hit"]
            rows.append(
                {
                    "Câu": answer["id"],
                    "Loại": QUESTION_TYPES_VI.get(answer["question_type"], answer["question_type"]),
                    "Tìm đúng bài": ok(answer["retrieval_hit"]),
                    "Độ khớp từ (F1)": round(answer["token_f1"], 2),
                    "Judge chấm đúng": ok(answer["judge"]["correct"]),
                    "Lỗi tác động vào bài": ", ".join(affected.get(paper_id, [])) or "—",
                    "Ghi chú": "⚠️ đúng chữ nhưng sai tài liệu" if silent else "",
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------------------------------------------------------------- CP5
with tabs[6]:
    st.subheader("CP5 · Tự động sửa từ dữ liệu gốc & so sánh 3 trạng thái")
    frame = metric_frame()
    if frame.empty or len(frame["state"].unique()) < 3:
        st.info("Chưa đủ 3 trạng thái — chạy Corruption Flow.")
    else:
        st.altair_chart(comparison_chart(frame), width="content")
        table = pd.DataFrame(
            {
                STATE_LABELS[s]: {
                    **{label: f"{metrics[s][key]:.3f}" for key, label in RATE_METRICS.items()},
                    JUDGE_SCORE_LABEL: f"{metrics[s]['mean_judge_score']:.2f}",
                    "Quality Gate": "✅ PASS" if quality[s] and quality[s]["success"] else "❌ FAIL",
                    "Độ mới dữ liệu": "✅ Còn mới" if quality[s] and quality[s]["freshness"]["is_fresh"] else "❌ Đã cũ",
                }
                for s in STATES
            }
        )
        st.dataframe(table, width="stretch")

        st.markdown("**Self-healing (bonus B2):** Quality Gate fail → tự động repair từ raw snapshot → kiểm tra lại")
        healing = load(SELF_HEALING_LOG) or []
        for step in healing:
            if step["step"] == "quality_gate":
                st.write(f"{ok(step['success'])} Quality Gate **{step['state']}**: {'PASS' if step['success'] else 'FAIL'}")
            else:
                reason = "tự động vì Quality Gate báo lỗi" if step["trigger"].startswith("auto") else "chạy theo lịch để so sánh"
                st.write(f"🔧 Sửa dữ liệu — {reason}, dựng lại từ `{step['source']}`")
    if paths.comparison_report.exists():
        with st.expander("Xem `corruption_report.md`"):
            st.markdown(paths.comparison_report.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- live QA
with tabs[7]:
    st.subheader("Hỏi cùng một câu trên 3 collection")
    st.caption("QA dùng luật trích xuất trong `retrieval/qa.py` (không gọi LLM), nên chạy tức thì và không tốn API.")
    available = [s for s in STATES if EMBEDDINGS[s].exists()]
    if not available:
        st.info("Chưa có index — chạy pipeline trước.")
    else:
        options = {f"{item['id']} · {item['question']}": item for item in test_set}
        choice = st.selectbox("Chọn câu trong test set", ["(tự nhập câu hỏi)", *options])
        item = options.get(choice)
        question = item["question"] if item else st.text_input("Câu hỏi", "Who authored the paper 'Freshness SLAs for Real-Time LLM Knowledge Augmentation'?")
        if item:
            st.markdown(f"**Đáp án chuẩn:** {item['ground_truth']}")
        cols = st.columns(len(available))
        for col, state in zip(cols, available):
            result = answer_question(question, settings=settings, index=get_index(state))
            with col, st.container(border=True):
                st.markdown(f"#### {STATE_LABELS[state]}")
                st.write(result.answer or "_(trả lời rỗng)_")
                if item:
                    hit = any(doc in item["ground_truth_doc_ids"] for doc in result.retrieved_doc_ids)
                    st.caption(f"Tìm đúng bài: {ok(hit)} · Token F1: {_token_f1(item['ground_truth'], result.answer):.2f}")
                st.caption("Top-k: " + " · ".join(title[:40] for title in result.retrieved_titles))

# ---------------------------------------------------------------- CP6
with tabs[8]:
    st.subheader("CP6 · Checklist trước khi nộp")

    def git(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        except OSError:
            return ""

    tracked = set(git("ls-files").splitlines())
    required = [
        "data/raw/crossref_response.json", "data/raw/crossref_records.json",
        "data/clean/papers_clean.csv", "data/clean/papers_clean.json", "data/eval/test_set.json",
        "data/results/baseline_metrics.json", "data/results/corrupted_metrics.json",
        "data/results/repaired_metrics.json", "data/results/corruption_log.json",
        "data/reports/phase1_report.md", "data/reports/corruption_report.md",
        "docs/TEAM.md", "docs/SUBMISSION.md", "docs/CHECKPOINTS.md", "docs/RUBRIC.md", ".env.example",
    ]
    st.dataframe(
        pd.DataFrame(
            [{"File": f, "Có trên máy": ok((ROOT / f).exists()), "Đã commit": ok(f in tracked)} for f in required]
        ),
        hide_index=True,
        width="stretch",
    )
    team_text = (ROOT / "docs" / "TEAM.md").read_text(encoding="utf-8")
    reports = sorted(p.name for p in (ROOT / "report").glob("2A*.md"))
    contributors = sorted(set(git("log", "origin/main", "--format=%an").splitlines()))
    st.markdown(
        f"""
- {ok('.env' not in tracked)} `.env` **không** bị commit
- {ok('[Điền' not in team_text and 'HoVaTen' not in team_text)} `docs/TEAM.md` đã điền
- {ok(len(reports) >= 4)} Báo cáo cá nhân `report/<MSSV>_HoTen.md`: {len(reports)}/4 — {', '.join(reports) or 'chưa có'}
- Contributors trên `origin/main`: {', '.join(contributors) or 'không đọc được'}
"""
    )
