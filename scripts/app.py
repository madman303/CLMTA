"""ClimateScope Streamlit dashboard."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(layout="wide", page_title="ClimateScope")

BASE_DIR = Path(__file__).resolve().parent.parent 

OUTPUTS = BASE_DIR / "outputs"
FIGURES = OUTPUTS / "figures"
DATA = BASE_DIR / "data"

@st.cache_data
def load_metrics() -> pd.DataFrame:
    """Load model backtest metrics."""
    return pd.read_csv(OUTPUTS / "forecast_horizon_metrics.csv")


@st.cache_data
def load_analysis_summary() -> dict:
    """Load trend and change-point analysis results."""
    with (OUTPUTS / "analysis_summary.json").open(encoding="utf-8") as file:
        return json.load(file)


@st.cache_data
def load_region_data(region: str) -> pd.DataFrame:
    """Return the latest 100 observations for a validated region."""
    import duckdb

    allowed_regions = {"Land_Ocean", "Land", "Ocean"}
    if region not in allowed_regions:
        raise ValueError(f"Unsupported region: {region}")

    with duckdb.connect(str(DATA / "clmta.duckdb"), read_only=True) as connection:
        tables = connection.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('main', 'marts')
            """
        ).fetchall()
        table_names = {(schema, name) for schema, name in tables}
        if ("main", "mart_monthly_anomaly") in table_names:
            table = "mart_monthly_anomaly"
            region_column = "region"
            region_value = region
            anomaly_column = '"Anomaly"'
        elif ("marts", "monthly_anomaly") in table_names:
            table = "marts.monthly_anomaly"
            region_column = "series"
            region_value = region.lower()
            anomaly_column = "anomaly"
        else:
            raise RuntimeError(
                "数据库中找不到 mart_monthly_anomaly 或 marts.monthly_anomaly 表"
            )

        query = f"""
            SELECT obs_date, {anomaly_column} AS Anomaly
            FROM {table}
            WHERE {region_column} = ?
            ORDER BY obs_date DESC
            LIMIT 100
        """
        result = connection.execute(query, [region_value]).fetchdf()
    return result.sort_values("obs_date").reset_index(drop=True)


def show_image(filename: str, caption: str | None = None) -> None:
    """Display an output image with a friendly missing-file message."""
    path = FIGURES / filename
    if not path.exists():
        st.warning(f"找不到图片文件：{path}")
        return
    st.image(str(path), caption=caption, use_container_width=True)


def show_overview() -> None:
    st.title("🌍 全球气候异常总览")
    show_image(
        "monthly_heatmap.png",
        "1850s至2020s，全球各月份温度异常值从浅蓝全面转变为深红，直观印证了全球变暖。",
    )
    show_image(
        "land_ocean_compare.png",
        "陆地升温速率显著快于海洋，存在明显的放大效应。",
    )


def show_trends() -> None:
    st.title("📈 趋势检验与变点分析")
    show_image("stl_decomposition.png")
    try:
        summary = load_analysis_summary()
        trend = summary["trend"]
        st.subheader("Mann-Kendall 趋势检验")
        first, second, third = st.columns(3)
        first.metric("P-value", f"{trend['p_value']:.4g}")
        second.metric("趋势斜率（每十年）", f"{trend['slope_per_decade']:.4f}")
        third.metric("检验方法", trend.get("method", "Mann-Kendall"))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        st.error(f"读取趋势分析结果失败：{error}")


def show_forecasts() -> None:
    st.title("🤖 多模型多步长预测对比")
    try:
        metrics = load_metrics()
        horizons = [1, 3, 6, 12, 24]
        selected_horizon = st.selectbox("选择预测 Horizon（月）", horizons)
        selected = metrics[metrics["horizon"] == selected_horizon].copy()
        if selected.empty:
            st.warning("该 Horizon 没有可用的回测结果。")
            return

        display_columns = ["model", "RMSE", "MASE"]
        selected = selected[display_columns].sort_values("RMSE")
        styled = selected.style.highlight_min(
            subset=["RMSE", "MASE"], color="#b7e4c7"
        ).format({"RMSE": "{:.4f}", "MASE": "{:.4f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)
        show_image(
            "forecast_horizon_rmse.png",
            "大模型（Chronos）在长短期表现优异，但特定周期被简单基线模型反杀。",
        )
    except (OSError, pd.errors.ParserError, KeyError, TypeError, ValueError) as error:
        st.error(f"读取预测评估结果失败：{error}")


def show_explorer() -> None:
    st.title("🗄️ 原始数据库查询")
    region = st.selectbox("选择 Region", ["Land_Ocean", "Land", "Ocean"])
    try:
        data = load_region_data(region)
        if data.empty:
            st.info("该 Region 没有查询到数据。")
            return
        data["obs_date"] = data["obs_date"].astype(str)
        st.line_chart(data.set_index("obs_date")["Anomaly"])
        st.dataframe(data, use_container_width=True, hide_index=True)
    except (OSError, ImportError, RuntimeError, ValueError) as error:
        st.error(f"数据库查询失败：{error}")


def main() -> None:
    page = st.sidebar.radio(
        "导航",
        ["数据概览", "趋势与分解", "模型回测", "数据探索"],
    )
    if page == "数据概览":
        show_overview()
    elif page == "趋势与分解":
        show_trends()
    elif page == "模型回测":
        show_forecasts()
    else:
        show_explorer()


if __name__ == "__main__":
    main()