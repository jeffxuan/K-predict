"""Generate AI-readable research notes for investment-contest reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_research_notes(
    runs: pd.DataFrame,
    multifactor_report: dict[str, Any] | None = None,
    output_path: str | Path = "outputs/research_log/research_notes.md",
) -> str:
    """Write a compact Chinese research log for report drafting."""

    report = multifactor_report or {}
    ranking = {item["ticker"]: item for item in report.get("multifactor_ranking", [])}
    weights = (report.get("document_portfolio") or {}).get("weights", {})
    macro = report.get("macro_holding_model") or {}
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# SCI/SIC 投资比赛研究日志")
    lines.append("")
    lines.append("这份日志用于沉淀 Kronos 预测、真实走势、误差表现和多因子背景，方便后续写投资比赛报告。")
    lines.append("它不是实盘交易建议；如果数据源是 demo/synthetic，需要在正式报告中替换为真实行情和真实财务数据。")
    lines.append("")
    if macro:
        lines.append("## 宏观仓位背景")
        lines.append(
            f"- 宏观综合分：{_fmt_float(macro.get('score'), 2)}；建议权益仓位：{_fmt_pct(macro.get('suggested_equity_exposure'))}。"
        )
        lines.append("- 比赛写作角度：该结果可作为组合不是满仓、但仍保持较高权益暴露的依据。")
        lines.append("")

    if runs.empty:
        lines.append("## 预测记录")
        lines.append("- 暂无可评估的 Kronos 预测结果。")
    else:
        lines.append("## 预测记录总览")
        evaluated = runs[runs["status"] == "evaluated"] if "status" in runs else pd.DataFrame()
        pending = runs[runs["status"] == "pending_actuals"] if "status" in runs else pd.DataFrame()
        lines.append(f"- 已评估预测次数：{len(evaluated)}。")
        lines.append(f"- 等待真实值的预测次数：{len(pending)}。")
        if len(evaluated):
            lines.append(
                f"- 平均方向准确率：{_fmt_pct(evaluated['direction_accuracy'].mean())}；"
                f"平均 close MAPE：{_fmt_pct(evaluated['close_mape'].mean())}。"
            )
        lines.append("")

        for ticker in sorted(runs["ticker"].fillna("UNKNOWN").unique()):
            ticker_runs = runs[runs["ticker"].fillna("UNKNOWN") == ticker].copy()
            lines.extend(_ticker_section(ticker, ticker_runs, ranking.get(ticker), weights.get(ticker)))

    lines.append("## 报告写作提示")
    lines.append("- 如果预测误差小且多因子分数高：可写成“技术面预测与基本面/ESG 共振”。")
    lines.append("- 如果预测误差大但多因子分数高：可写成“短期价格模型存在噪声，长期配置仍由基本面支撑”。")
    lines.append("- 如果方向准确率低：应放入风险控制或模型局限性段落，说明不会只依赖 K 线模型。")
    lines.append("- 如果某次预测缺少真实值：只作为待验证观察，不作为最终结论。")
    lines.append("")

    content = "\n".join(lines)
    output.write_text(content, encoding="utf-8")
    return content


def _ticker_section(ticker: str, runs: pd.DataFrame, factor: dict[str, Any] | None, weight: float | None) -> list[str]:
    lines = [f"## {ticker}"]
    evaluated = runs[runs["status"] == "evaluated"] if "status" in runs else pd.DataFrame()
    pending = runs[runs["status"] == "pending_actuals"] if "status" in runs else pd.DataFrame()
    lines.append(f"- 预测记录：{len(runs)} 次；已评估：{len(evaluated)} 次；待验证：{len(pending)} 次。")
    if weight is not None:
        lines.append(f"- 文档组合目标权重：{_fmt_pct(weight)}。")
    if factor:
        lines.append(
            "- 多因子背景："
            f"行业={factor.get('industry', 'N/A')}，"
            f"综合分={_fmt_float(factor.get('combined_score'), 2)}，"
            f"基本面分={_fmt_float(factor.get('fundamental_score'), 2)}，"
            f"ESG分={_fmt_float(factor.get('esg_score'), 2)}，"
            f"MSCI={factor.get('msci_rating', 'N/A')}，"
            f"Sustainalytics={_fmt_float(factor.get('sustainalytics_score'), 1)}。"
        )
    if len(evaluated):
        best = evaluated.sort_values("close_mape", ascending=True).iloc[0]
        worst = evaluated.sort_values("close_mape", ascending=False).iloc[0]
        lines.append(
            f"- 平均 close MAPE：{_fmt_pct(evaluated['close_mape'].mean())}；"
            f"平均方向准确率：{_fmt_pct(evaluated['direction_accuracy'].mean())}；"
            f"平均收益误差：{_fmt_pct(evaluated['return_error'].mean())}。"
        )
        lines.append(
            f"- 最稳定预测：run_id={best['run_id']}，close MAPE={_fmt_pct(best.get('close_mape'))}，"
            f"预测收益={_fmt_pct(best.get('predicted_return'))}，真实收益={_fmt_pct(best.get('actual_return'))}。"
        )
        lines.append(
            f"- 最大偏差案例：run_id={worst['run_id']}，close MAPE={_fmt_pct(worst.get('close_mape'))}，"
            f"可作为模型局限性或风险控制材料。"
        )
    else:
        lines.append("- 暂无真实值对比，当前只能作为预测观察记录。")
    lines.append("")
    return lines


def _fmt_pct(value: Any) -> str:
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_float(value: Any, digits: int = 2) -> str:
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"
