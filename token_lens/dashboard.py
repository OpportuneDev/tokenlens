"""
Streamlit dashboard — run with: token-lens dashboard
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

from token_lens.store import read, clear

st.set_page_config(
    page_title="token-lens",
    page_icon="🔍",
    layout="wide",
)

# Auto-refresh every 3s when a browser is connected
st_autorefresh(interval=3000)

# ── Load data ────────────────────────────────────────────────────────────────
records = read()

# ── Header ───────────────────────────────────────────────────────────────────
col_title, col_clear = st.columns([6, 1])
with col_title:
    st.title("token-lens")
    st.caption("Token waste diagnostic — live session view")
with col_clear:
    st.write("")
    st.write("")
    if st.button("Clear session", type="secondary"):
        clear()
        st.rerun()

if not records:
    st.info("No calls recorded yet. Run your app with `token_lens.patch()` to start capturing.")
    st.code("import token_lens\ntoken_lens.patch()\n\n# then run your app as normal", language="python")
    st.stop()

df = pd.DataFrame(records)
df["ts"] = pd.to_datetime(df["ts"], unit="s")
df["call"] = [f"#{i+1}" for i in range(len(df))]

# ── Top metrics ──────────────────────────────────────────────────────────────
st.divider()
m1, m2, m3, m4 = st.columns(4)

total_calls  = len(df)
avg_score    = df["efficiency_score"].mean()
total_wasted = df["recoverable_tokens"].sum()
total_input  = df["total_input_tokens"].sum()
waste_pct    = (total_wasted / total_input * 100) if total_input else 0

m1.metric("Calls captured", total_calls)
m2.metric("Avg efficiency",  f"{avg_score:.0f}/100")
m3.metric("Tokens wasted",   f"{total_wasted:,}")
m4.metric("Waste %",         f"{waste_pct:.1f}%")

st.divider()

# ── Efficiency score over time ────────────────────────────────────────────────
left, right = st.columns([2, 1])

with left:
    st.subheader("Efficiency per call")
    fig_score = px.line(
        df, x="call", y="efficiency_score",
        markers=True,
        color_discrete_sequence=["#4f8bf9"],
    )
    fig_score.add_hline(y=80, line_dash="dash", line_color="green",  annotation_text="Good (80)")
    fig_score.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="Warn (50)")
    fig_score.update_layout(
        yaxis_range=[0, 105],
        yaxis_title="Efficiency score",
        xaxis_title="",
        margin=dict(t=10, b=10),
        height=280,
    )
    st.plotly_chart(fig_score, width="stretch")

with right:
    st.subheader("Token composition (last call)")
    last = records[-1]
    seg_df = pd.DataFrame(last["segments"])
    fig_pie = px.pie(
        seg_df, names="name", values="tokens",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        hole=0.4,
    )
    fig_pie.update_layout(margin=dict(t=10, b=10), height=280, showlegend=True)
    st.plotly_chart(fig_pie, width="stretch")

# ── Token usage per call ──────────────────────────────────────────────────────
st.subheader("Token usage per call")
fig_tokens = go.Figure()
fig_tokens.add_bar(x=df["call"], y=df["total_input_tokens"],       name="Input tokens",  marker_color="#4f8bf9")
fig_tokens.add_bar(x=df["call"], y=df["output_tokens"].fillna(0),  name="Output tokens", marker_color="#f9a84f")
fig_tokens.update_layout(
    barmode="stack",
    height=220,
    margin=dict(t=10, b=10),
    yaxis_title="Tokens",
    xaxis_title="",
)
st.plotly_chart(fig_tokens, width="stretch")

st.divider()

# ── Waste flags ───────────────────────────────────────────────────────────────
st.subheader("Waste flags — all calls")

all_flags = []
for i, rec in enumerate(records):
    for flag in rec["flags"]:
        all_flags.append({
            "Call":          f"#{i+1}",
            "Model":         rec["model"],
            "Severity":      flag["severity"],
            "Pattern":       flag["pattern"],
            "Tokens wasted": flag["tokens_wasted"],
            "Fix":           flag["fix"],
        })

if all_flags:
    flags_df = pd.DataFrame(all_flags)

    def severity_color(val):
        return {
            "HIGH":   "background-color: #ffe0e0",
            "MEDIUM": "background-color: #fff3cd",
            "LOW":    "background-color: #e0f0ff",
        }.get(val, "")

    st.dataframe(
        flags_df.style.map(severity_color, subset=["Severity"]),
        width="stretch",
        hide_index=True,
    )
else:
    st.success("No waste flags detected across this session.")
