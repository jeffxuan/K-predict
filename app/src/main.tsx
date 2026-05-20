import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  Github,
  Globe2,
  Languages,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import "./styles.css";

type Language = "zh" | "en";
type Page = "overview" | "data" | "run" | "audit" | "notes" | "guide";

type Status = {
  tickers: string[];
  models: Array<{ id: string; label: string; context_length: number; available: boolean }>;
  macro: { score?: number; suggested_equity_exposure?: number };
  ranking: Ranking[];
  documentPortfolio: { weights?: Record<string, number>; metrics?: Record<string, number> };
  latestRuns: PredictionRun[];
  kronosAvailable: boolean;
};

type Ranking = {
  ticker: string;
  industry: string;
  combined_score: number;
  fundamental_score: number;
  esg_score: number;
  msci_rating: string;
  sustainalytics_score: number;
};

type PredictionRun = {
  run_id: string;
  ticker: string;
  status: string;
  model: string;
  timestamp: string;
  predicted_return: number;
  actual_return: number;
  return_error: number;
  close_mape: number;
  direction_accuracy: number;
  max_close_deviation_pct: number;
};

type FileItem = {
  path: string;
  label: string;
  purpose: string;
  exists: boolean;
  updatedAt: string | null;
  size: number | null;
  generatedBy: string;
  reportReady: boolean;
  dataSource: string;
};

type ResearchLog = {
  runs: PredictionRun[];
  pointsPreview: unknown[];
  notes: string;
  multifactor: Status;
};

const text = {
  zh: {
    product: "K-predict 研究工作台",
    subtitle: "为 SCI/SIC 投资比赛准备的 Kronos + 多因子研究助手",
    overview: "总览",
    data: "数据文件",
    run: "运行预测",
    audit: "误差审计",
    notes: "研究日志",
    guide: "操作指南",
    refresh: "刷新",
    language: "English",
    macroScore: "宏观分",
    equityExposure: "建议权益仓位",
    latestRuns: "最近预测",
    ranking: "多因子排序",
    portfolio: "文档组合",
    noRuns: "还没有 UI 预测记录。先去运行预测。",
    filePurpose: "用途",
    dataSource: "数据源",
    updated: "更新",
    reportReady: "可写入报告",
    exists: "存在",
    missing: "缺失",
    runTitle: "一键运行 Kronos",
    runHelp: "选择股票、模型和窗口。结果会自动保存并刷新研究日志。",
    ticker: "股票",
    model: "模型",
    lookback: "历史窗口",
    predLen: "预测长度",
    temperature: "温度",
    sampleCount: "样本数",
    startRun: "开始预测",
    running: "Kronos 正在运行，请稍等",
    runSuccess: "预测完成并已记录",
    runError: "预测失败",
    auditTitle: "预测误差审计",
    auditRefresh: "刷新审计",
    mape: "Close MAPE",
    direction: "方向准确率",
    predReturn: "预测收益",
    actualReturn: "真实收益",
    returnError: "收益误差",
    maxDeviation: "最大偏离",
    copy: "复制日志",
    copied: "已复制",
    guideIntro: "推荐工作流",
    disclaimer: "所有结果仅用于比赛研究和报告材料，不构成实盘交易建议。",
  },
  en: {
    product: "K-predict Workbench",
    subtitle: "Kronos + multi-factor research assistant for SCI/SIC investment contests",
    overview: "Overview",
    data: "Data Library",
    run: "Run Prediction",
    audit: "Error Audit",
    notes: "Research Notes",
    guide: "Guide",
    refresh: "Refresh",
    language: "中文",
    macroScore: "Macro score",
    equityExposure: "Equity exposure",
    latestRuns: "Latest runs",
    ranking: "Multi-factor ranking",
    portfolio: "Document portfolio",
    noRuns: "No UI prediction runs yet. Start from Run Prediction.",
    filePurpose: "Purpose",
    dataSource: "Data source",
    updated: "Updated",
    reportReady: "Report ready",
    exists: "Exists",
    missing: "Missing",
    runTitle: "Run Kronos",
    runHelp: "Choose ticker, model, and window. Results are saved and audited automatically.",
    ticker: "Ticker",
    model: "Model",
    lookback: "Lookback",
    predLen: "Prediction length",
    temperature: "Temperature",
    sampleCount: "Sample count",
    startRun: "Start prediction",
    running: "Kronos is running. Please wait.",
    runSuccess: "Prediction completed and recorded",
    runError: "Prediction failed",
    auditTitle: "Prediction error audit",
    auditRefresh: "Refresh audit",
    mape: "Close MAPE",
    direction: "Direction accuracy",
    predReturn: "Predicted return",
    actualReturn: "Actual return",
    returnError: "Return error",
    maxDeviation: "Max deviation",
    copy: "Copy notes",
    copied: "Copied",
    guideIntro: "Recommended workflow",
    disclaimer: "All outputs are contest research materials, not live trading advice.",
  },
};

const nav: Array<readonly [Page, React.ComponentType<{ size?: number }>]> = [
  ["overview", Activity],
  ["data", Database],
  ["run", Play],
  ["audit", BarChart3],
  ["notes", FileText],
  ["guide", BookOpen],
] as const;

function App() {
  const [lang, setLang] = useState<Language>("zh");
  const [page, setPage] = useState<Page>("overview");
  const [status, setStatus] = useState<Status | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [log, setLog] = useState<ResearchLog | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const t = text[lang];

  async function refresh() {
    const [statusRes, filesRes, logRes] = await Promise.all([
      fetch("/api/workbench/status"),
      fetch("/api/workbench/files"),
      fetch("/api/workbench/research-log"),
    ]);
    setStatus(await statusRes.json());
    setFiles(await filesRes.json());
    setLog(await logRes.json());
  }

  useEffect(() => {
    refresh().catch((error) => setMessage(String(error)));
  }, []);

  const latestRuns = log?.runs?.length ? log.runs : status?.latestRuns || [];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandIcon"><ShieldCheck size={20} /></div>
          <div>
            <strong>{t.product}</strong>
            <span>SCI/SIC</span>
          </div>
        </div>
        <nav>
          {nav.map(([key, Icon]) => (
            <button key={key} className={page === key ? "nav active" : "nav"} onClick={() => setPage(key)}>
              <Icon size={18} />
              {t[key]}
            </button>
          ))}
        </nav>
        <p className="sideNote">{t.disclaimer}</p>
        <a className="githubCredit" href="https://github.com/jeffxuan/K-predict" target="_blank" rel="noreferrer">
          <Github size={16} />
          <span>GitHub</span>
          <strong>jeffxuan/K-predict</strong>
        </a>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{t.product}</h1>
            <p>{t.subtitle}</p>
          </div>
          <div className="topActions">
            <button className="ghost" onClick={() => setLang(lang === "zh" ? "en" : "zh")}>
              <Languages size={17} /> {t.language}
            </button>
            <button className="ghost" onClick={() => refresh()}>
              <RefreshCw size={17} /> {t.refresh}
            </button>
          </div>
        </header>

        {message && <div className="notice">{message}</div>}
        {page === "overview" && <Overview t={t} status={status} runs={latestRuns} />}
        {page === "data" && <DataLibrary t={t} files={files} />}
        {page === "run" && (
          <RunPrediction
            t={t}
            status={status}
            busy={busy}
            setBusy={setBusy}
            setMessage={setMessage}
            refresh={refresh}
          />
        )}
        {page === "audit" && <Audit t={t} runs={latestRuns} refresh={refresh} setMessage={setMessage} />}
        {page === "notes" && <Notes t={t} notes={log?.notes || ""} />}
        {page === "guide" && <Guide t={t} lang={lang} />}
      </main>
    </div>
  );
}

function Overview({ t, status, runs }: { t: any; status: Status | null; runs: PredictionRun[] }) {
  const weights = status?.documentPortfolio?.weights || {};
  return (
    <div className="grid">
      <Metric title={t.macroScore} value={fmtNumber(status?.macro?.score)} icon={<Globe2 />} />
      <Metric title={t.equityExposure} value={fmtPct(status?.macro?.suggested_equity_exposure)} icon={<Activity />} />
      <Metric title={t.latestRuns} value={String(runs.length)} icon={<ClipboardList />} />
      <section className="panel wide">
        <h2>{t.ranking}</h2>
        <div className="table">
          {(status?.ranking || []).map((item) => (
            <div className="row" key={item.ticker}>
              <strong>{item.ticker}</strong>
              <span>{item.industry}</span>
              <span>{fmtNumber(item.combined_score)}</span>
              <span>MSCI {item.msci_rating}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>{t.portfolio}</h2>
        {Object.entries(weights).map(([ticker, weight]) => (
          <div className="weight" key={ticker}>
            <span>{ticker}</span>
            <div><i style={{ width: `${weight * 100}%` }} /></div>
            <b>{fmtPct(weight)}</b>
          </div>
        ))}
      </section>
      <RunsPanel t={t} runs={runs} />
    </div>
  );
}

function Metric({ title, value, icon }: { title: string; value: string; icon: React.ReactNode }) {
  return (
    <section className="metric">
      <div>{icon}</div>
      <span>{title}</span>
      <strong>{value}</strong>
    </section>
  );
}

function DataLibrary({ t, files }: { t: any; files: FileItem[] }) {
  return (
    <section className="panel full">
      <h2>{t.data}</h2>
      <div className="fileGrid">
        {files.map((file) => (
          <article className="fileCard" key={file.path}>
            <div className="fileHead">
              <Database size={18} />
              <strong>{file.label}</strong>
              <span className={file.exists ? "badge ok" : "badge bad"}>{file.exists ? t.exists : t.missing}</span>
            </div>
            <code>{file.path}</code>
            <p>{file.purpose}</p>
            <dl>
              <dt>{t.dataSource}</dt><dd>{file.dataSource}</dd>
              <dt>{t.updated}</dt><dd>{file.updatedAt ? new Date(file.updatedAt).toLocaleString() : "N/A"}</dd>
              <dt>{t.reportReady}</dt><dd>{file.reportReady ? "Yes" : "No"}</dd>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function RunPrediction({ t, status, busy, setBusy, setMessage, refresh }: any) {
  const [ticker, setTicker] = useState("ADBE");
  const [model, setModel] = useState("kronos-base");
  const [lookback, setLookback] = useState(400);
  const [predLen, setPredLen] = useState(30);
  const [temperature, setTemperature] = useState(1);
  const [sampleCount, setSampleCount] = useState(1);

  async function run() {
    setBusy(true);
    setMessage(t.running);
    try {
      const response = await fetch("/api/workbench/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, model, lookback, pred_len: predLen, temperature, top_p: 0.9, sample_count: sampleCount }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || t.runError);
      setMessage(`${t.runSuccess}: ${ticker} ${model}`);
      await refresh();
    } catch (error) {
      setMessage(`${t.runError}: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel runPanel">
      <h2>{t.runTitle}</h2>
      <p className="muted">{t.runHelp}</p>
      <div className="formGrid">
        <label>{t.ticker}<select value={ticker} onChange={(e) => setTicker(e.target.value)}>{(status?.tickers || ["ADBE", "LLY", "GOOGL"]).map((x: string) => <option key={x}>{x}</option>)}</select></label>
        <label>{t.model}<select value={model} onChange={(e) => setModel(e.target.value)}>{(status?.models || []).map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
        <label>{t.lookback}<input type="number" value={lookback} onChange={(e) => setLookback(Number(e.target.value))} /></label>
        <label>{t.predLen}<input type="number" value={predLen} onChange={(e) => setPredLen(Number(e.target.value))} /></label>
        <label>{t.temperature}<input type="number" step="0.1" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} /></label>
        <label>{t.sampleCount}<input type="number" value={sampleCount} onChange={(e) => setSampleCount(Number(e.target.value))} /></label>
      </div>
      <button className="primary" disabled={busy} onClick={run}>
        {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />} {busy ? t.running : t.startRun}
      </button>
    </section>
  );
}

function Audit({ t, runs, refresh, setMessage }: any) {
  async function audit() {
    const response = await fetch("/api/workbench/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results_dir: "outputs/ui_predictions" }),
    });
    const payload = await response.json();
    setMessage(payload.success ? `${t.auditRefresh}: ${payload.runCount}` : JSON.stringify(payload));
    await refresh();
  }
  return (
    <section className="panel full">
      <div className="sectionHead">
        <h2>{t.auditTitle}</h2>
        <button className="ghost" onClick={audit}><RefreshCw size={16} /> {t.auditRefresh}</button>
      </div>
      <RunsPanel t={t} runs={runs} />
    </section>
  );
}

function RunsPanel({ t, runs }: { t: any; runs: PredictionRun[] }) {
  if (!runs?.length) return <section className="panel"><h2>{t.latestRuns}</h2><p className="muted">{t.noRuns}</p></section>;
  return (
    <section className="panel wide">
      <h2>{t.latestRuns}</h2>
      <div className="runTable">
        <div className="runHeader"><span>{t.ticker}</span><span>{t.model}</span><span>{t.predReturn}</span><span>{t.actualReturn}</span><span>{t.mape}</span><span>{t.direction}</span></div>
        {runs.slice().reverse().map((run) => (
          <div className="runRow" key={run.run_id}>
            <strong>{run.ticker}</strong>
            <span>{run.model}</span>
            <span>{fmtPct(run.predicted_return)}</span>
            <span>{fmtPct(run.actual_return)}</span>
            <span>{fmtPct(run.close_mape)}</span>
            <span>{fmtPct(run.direction_accuracy)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function Notes({ t, notes }: { t: any; notes: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <section className="panel full">
      <div className="sectionHead">
        <h2>{t.notes}</h2>
        <button className="ghost" onClick={() => { navigator.clipboard.writeText(notes); setCopied(true); }}>
          <ClipboardList size={16} /> {copied ? t.copied : t.copy}
        </button>
      </div>
      <pre className="notes">{notes || "No research notes yet."}</pre>
    </section>
  );
}

function Guide({ t, lang }: { t: any; lang: Language }) {
  const steps = lang === "zh"
    ? ["检查数据文件：确认 Kronos 输入、财务、ESG、宏观和组合文件都存在。", "在运行预测页选择股票和模型。建议报告展示用 Kronos-base，快速试验用 mini。", "点击开始预测，等待模型完成。结果会保存为 JSON。", "到误差审计页查看 MAPE、方向准确率和收益误差。", "到研究日志页复制可用材料，写入比赛报告。"]
    : ["Check Data Library and confirm Kronos input, fundamentals, ESG, macro, and portfolio files exist.", "Choose ticker and model. Use Kronos-base for report evidence, mini for quick trials.", "Run prediction and wait for model completion. Results are saved as JSON.", "Review MAPE, direction accuracy, and return error in Error Audit.", "Copy Research Notes into your contest report draft."];
  return (
    <section className="panel guide full">
      <h2>{t.guideIntro}</h2>
      {steps.map((step, index) => (
        <div className="step" key={step}>
          <b>{index + 1}</b>
          <p>{step}</p>
        </div>
      ))}
      <div className="notice"><CheckCircle2 size={18} /> {t.disclaimer}</div>
    </section>
  );
}

function fmtPct(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return "N/A";
  return `${(value * 100).toFixed(2)}%`;
}

function fmtNumber(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return "N/A";
  return value.toFixed(2);
}

createRoot(document.getElementById("root")!).render(<App />);
