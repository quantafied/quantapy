import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Calculator,
  ChevronDown,
  Columns3,
  Database,
  FlaskConical,
  GripVertical,
  KeyRound,
  LineChart,
  Play,
  RefreshCw,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import Plotly from "plotly.js-dist-min";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
type PlotlyTrace = Record<string, unknown>;
type PlotlyLayout = Record<string, unknown>;

type JsonSchema = {
  title?: string;
  type?: string;
  default?: unknown;
  enum?: unknown[];
  widget_type?: string;
  use_variable_options?: boolean;
  show_if?: Record<string, unknown>;
  items?: JsonSchema;
  properties?: Record<string, JsonSchema>;
};

type Components = Record<string, Record<string, Record<string, { title?: string; properties?: Record<string, JsonSchema> }>>>;

type ExecutorSection = {
  key: string;
  label: string;
  component_category?: string;
  multiple?: boolean;
  default_function?: string;
  default_source?: string;
  column_options?: boolean;
};

type ExecutorMetadata = {
  runner: string;
  label: string;
  domain?: string;
  template_type?: string;
  input_contract?: Record<string, unknown>;
  config_schema?: { title?: string; properties?: Record<string, JsonSchema> };
  config_builder?: {
    mode?: string;
    sections?: ExecutorSection[];
  };
  template_format?: string;
};

type Executors = Record<string, ExecutorMetadata>;

type EvaluatorMetadata = {
  evaluator: string;
  label: string;
  domain?: string;
  input_contract?: Record<string, unknown>;
  config_schema?: { title?: string; properties?: Record<string, JsonSchema> };
  output_contract?: Record<string, unknown>;
};

type Evaluators = Record<string, EvaluatorMetadata>;

type StoreRecord = {
  id: string;
  name: string;
  label: string;
  kind: string;
  artifact: string | null;
  run_id: string | null;
  fold: number | null;
  split: string | null;
  phase: string | null;
  internal: boolean;
  shape: [number, number];
  columns: string[];
  attrs: Record<string, unknown>;
  transform?: { name?: string; operations?: CalculatorOperation[] } | null;
  parents: Array<{ id: string; name: string }>;
  children: Array<{ id: string; name: string }>;
};

type ArtifactRecord = {
  id: string;
  name: string;
  artifact_type: string;
  role: string;
  uri?: string | null;
  parent_ids: string[];
  dataframe_id?: string | null;
  metadata: Record<string, unknown>;
  provenance: Record<string, unknown>;
};

type StoreNode = Omit<StoreRecord, "parents" | "children"> & {
  parent_ids: string[];
  child_ids: string[];
  children: StoreNode[];
};

type StudyRun = {
  run_id: string;
  label: string;
  folds: number[];
  artifacts: StoreRecord[];
};

type ComponentSpec = {
  category: string;
  function: string;
  source: string;
  name?: string | null;
  params: Record<string, unknown>;
};

type TemplateSectionState = {
  function: string;
  source: string;
  params: Record<string, unknown>;
  items: ComponentSpec[];
};

type WorkspaceModel = {
  transforms: Array<{ id: string; name: string; transforms: ComponentSpec[] }>;
  strategies: Array<{ id: string; name: string; runner?: string; signals: ComponentSpec[]; orders: ComponentSpec[] }>;
  simulations: Array<{ id: string; name: string; simulation: ComponentSpec; evaluator?: ComponentSpec | null }>;
  templates?: Array<{ id: string; name: string; runner: string; sections: Record<string, unknown>; config?: Record<string, unknown> }>;
  executions?: {
    specs: Array<{ id: string; runner: string; name: string; attrs?: Record<string, unknown> }>;
    runs: Array<{
      id: string;
      spec_id: string;
      runner?: string | null;
      input_ids: string[];
      output_ids: string[];
      attrs?: Record<string, unknown>;
    }>;
  };
  evaluations?: {
    specs: Array<{ id: string; evaluator: string; name: string; attrs?: Record<string, unknown> }>;
    runs: Array<{
      id: string;
      spec_id: string;
      evaluator: string;
      source_run_id?: string | null;
      input_ids: string[];
      output_ids: string[];
      attrs?: Record<string, unknown>;
    }>;
  };
  active?: { transform_set_id?: string | null; strategy_id?: string | null; simulation_id?: string | null; execution_template_id?: string | null };
};

type StoreSummary = {
  workspace_id: string;
  latest_run_id: string | null;
  records: StoreRecord[];
  artifacts?: ArtifactRecord[];
  visible_records: StoreRecord[];
  navigation: StoreNode[];
  study_runs: StudyRun[];
  workspace?: WorkspaceModel;
  grouped: Record<string, StoreRecord[]>;
};

type FrameResponse = {
  record: StoreRecord;
  columns: string[];
  rows: Array<Record<string, number | string | null>>;
};

type TextArtifactResponse = {
  artifact: ArtifactRecord;
  text: string;
};

type CollectionResponse = {
  store: StoreSummary;
  collection: ArtifactRecord;
  dataset_ids: string[];
  artifact_ids: string[];
};

type ChartType = "ohlc" | "timeseries" | "scatter2d" | "scatter3d" | "table" | "metrics" | "text" | "calculator";
type ChartDatasetRole =
  | "fixed"
  | "source"
  | "signals"
  | "portfolio_outputs"
  | "portfolio_metrics"
  | "events"
  | "trials"
  | "fold_summary";

type ChartConfig = {
  id: string;
  type: ChartType;
  title: string;
  datasetId: string | null;
  collectionId?: string | null;
  collectionMode?: "selected" | "all";
  collectionIndex?: number;
  artifactId?: string | null;
  datasetRole?: ChartDatasetRole;
  signalDatasetId?: string | null;
  signalDatasetRole?: ChartDatasetRole;
  width?: "normal" | "wide" | "full";
  height?: "normal" | "tall";
  widthUnits?: number;
  heightPx?: number;
  maxRows?: number;
  mappings: {
    x?: string;
    y?: string[];
    open?: string;
    high?: string;
    low?: string;
    close?: string;
    z?: string;
    color?: string;
  };
};

type BasicOperation =
  | "add"
  | "subtract"
  | "multiply"
  | "divide"
  | "diff"
  | "pct_change"
  | "rolling_mean"
  | "rolling_std"
  | "normalize"
  | "zscore";

type CalculatorOperation = {
  id?: string;
  type: "basic" | "registered";
  name?: string;
  operation?: BasicOperation;
  left?: string;
  right?: string | null;
  scalar?: number | null;
  window?: number | null;
  output?: string;
  transforms?: Array<{
    id?: string;
    category: string;
    function: string;
    source: string;
    name?: string;
    params: Record<string, unknown>;
  }>;
};

type DashboardLayout = {
  id: string;
  name: string;
  charts: ChartConfig[];
};

type CollectionLeaf = {
  label: string;
  record: StoreRecord;
  path: string[];
};

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function canChart(record: StoreRecord | null): boolean {
  if (!record) return false;
  return ["open", "high", "low", "close"].every((column) => record.columns.includes(column));
}

function numericColumns(record: StoreRecord | null): string[] {
  return record?.columns.filter((column) => !["date"].includes(column)) ?? [];
}

function artifactOf(record: StoreRecord | null | undefined): string | null {
  if (!record) return null;
  return record.artifact ?? (typeof record.attrs.artifact === "string" ? record.attrs.artifact : null);
}

function collectionMemberDatasetIds(artifacts: ArtifactRecord[]): Set<string> {
  const artifactsById = new Map(artifacts.map((artifact) => [artifact.id, artifact]));
  const datasetIds = new Set<string>();

  function visit(artifact: ArtifactRecord | undefined) {
    if (!artifact || artifact.artifact_type !== "collection") return;
    const members = artifact.metadata.members;
    if (!Array.isArray(members)) return;
    for (const member of members) {
      if (!member || typeof member !== "object") continue;
      const item = member as Record<string, unknown>;
      if (typeof item.dataset_id === "string") datasetIds.add(item.dataset_id);
      if (typeof item.artifact_id === "string") visit(artifactsById.get(item.artifact_id));
    }
  }

  for (const artifact of artifacts) visit(artifact);
  return datasetIds;
}

function collectionMemberArtifactIds(artifacts: ArtifactRecord[]): Set<string> {
  const artifactsById = new Map(artifacts.map((artifact) => [artifact.id, artifact]));
  const artifactIds = new Set<string>();

  function visit(artifact: ArtifactRecord | undefined) {
    if (!artifact || artifact.artifact_type !== "collection") return;
    const members = artifact.metadata.members;
    if (!Array.isArray(members)) return;
    for (const member of members) {
      if (!member || typeof member !== "object") continue;
      const item = member as Record<string, unknown>;
      if (typeof item.artifact_id === "string") {
        artifactIds.add(item.artifact_id);
        visit(artifactsById.get(item.artifact_id));
      }
    }
  }

  for (const artifact of artifacts) visit(artifact);
  return artifactIds;
}

function filterMemberNodes(nodes: StoreNode[], memberIds: Set<string>): StoreNode[] {
  return nodes
    .filter((node) => !memberIds.has(node.id))
    .map((node) => ({ ...node, children: filterMemberNodes(node.children, memberIds) }));
}

function artifactMembers(artifact: ArtifactRecord | null | undefined): Array<Record<string, unknown>> {
  const members = artifact?.metadata?.members;
  return Array.isArray(members) ? members.filter((member): member is Record<string, unknown> => Boolean(member) && typeof member === "object") : [];
}

function collectionLeafRecordsFromStore(
  store: StoreSummary | null,
  collection: ArtifactRecord | null | undefined,
): CollectionLeaf[] {
  const artifactsById = new Map((store?.artifacts ?? []).map((artifact) => [artifact.id, artifact]));
  const recordsById = new Map((store?.records ?? []).map((record) => [record.id, record]));
  const leaves: CollectionLeaf[] = [];

  function visit(artifact: ArtifactRecord | null | undefined, path: string[]) {
    if (!artifact) return;
    if (artifact.artifact_type !== "collection") {
      const record = artifact.dataframe_id ? recordsById.get(artifact.dataframe_id) : undefined;
      if (record) leaves.push({ label: path.at(-1) || artifact.name, record, path });
      return;
    }
    for (const member of artifactMembers(artifact)) {
      const label = String(member.label ?? member.split ?? member.sample_index ?? "member");
      const childArtifactId = typeof member.artifact_id === "string" ? member.artifact_id : "";
      const childDatasetId = typeof member.dataset_id === "string" ? member.dataset_id : "";
      const childArtifact = artifactsById.get(childArtifactId);
      if (childArtifact) {
        visit(childArtifact, [...path, label]);
      } else if (childDatasetId) {
        const record = recordsById.get(childDatasetId);
        if (record) leaves.push({ label, record, path: [...path, label] });
      }
    }
  }

  visit(collection, collection ? [collection.name] : []);
  return leaves;
}

function leafFold(leaf: CollectionLeaf): string | null {
  if (leaf.record.fold !== null && leaf.record.fold !== undefined) return String(leaf.record.fold);
  const text = `${leaf.label} ${leaf.record.split ?? ""} ${leaf.path.join(" ")}`;
  const match = text.match(/fold[_\s-]*(\d+)/i);
  return match ? match[1] : null;
}

function leafSplit(leaf: CollectionLeaf): string | null {
  const direct = typeof leaf.record.split === "string" ? leaf.record.split.toLowerCase() : "";
  const text = `${leaf.label} ${direct} ${leaf.path.join(" ")}`.toLowerCase();
  if (/\btrain\b|_train\b|-train\b/.test(text)) return "train";
  if (/\bval\b|_val\b|-val\b|\bvalidation\b/.test(text)) return "val";
  if (/\btest\b|_test\b|-test\b/.test(text)) return "test";
  return null;
}

function leafSample(leaf: CollectionLeaf): string | null {
  const sample = leaf.record.attrs.sample_index;
  if (typeof sample === "number" || typeof sample === "string") return String(sample);
  const text = `${leaf.label} ${leaf.path.join(" ")}`;
  const match = text.match(/sample[_\s-]*(\d+)/i);
  return match ? match[1] : null;
}

function filterCollectionLeaves(
  leaves: CollectionLeaf[],
  activeFold: string,
  activeSplit: string,
): CollectionLeaf[] {
  return leaves.filter((leaf) => {
    const fold = leafFold(leaf);
    const split = leafSplit(leaf);
    const foldMatches = activeFold === "all" || !fold || fold === activeFold;
    const splitMatches = !split || split === activeSplit;
    return foldMatches && splitMatches;
  });
}

function collectionLeafSummary(leaves: CollectionLeaf[]) {
  const samples = new Set(leaves.map(leafSample).filter((value): value is string => Boolean(value)));
  const folds = new Set(leaves.map(leafFold).filter((value): value is string => Boolean(value)));
  const splits = new Set(leaves.map(leafSplit).filter((value): value is string => Boolean(value)));
  const columns = new Set(leaves.flatMap((leaf) => leaf.record.columns));
  const rows = leaves.reduce((total, leaf) => total + leaf.record.shape[0], 0);
  return {
    leaves: leaves.length,
    samples: samples.size,
    folds: folds.size,
    splits: Array.from(splits).sort((a, b) => ["train", "val", "test"].indexOf(a) - ["train", "val", "test"].indexOf(b)),
    columns: columns.size,
    rows,
  };
}

function frameNumericColumns(frame: FrameResponse | null): string[] {
  if (!frame) return [];
  return frame.columns.filter((column) => frame.rows.some((row) => numberValue(row[column]) !== null));
}

function mappingsForFrame(chart: ChartConfig, frame: FrameResponse | null): ChartConfig["mappings"] {
  if (chart.datasetRole !== "trials" || !frame) return chart.mappings;
  const numeric = frameNumericColumns(frame);
  const currentY = chart.mappings.y?.find((column) => numeric.includes(column));
  const x = frame.columns.includes(chart.mappings.x ?? "") && numeric.includes(chart.mappings.x ?? "")
    ? chart.mappings.x
    : numeric.includes("number")
      ? "number"
      : numeric[0];
  const y =
    currentY ??
    (numeric.includes("value")
      ? "value"
      : numeric.find((column) => column.startsWith("values_")) ??
        numeric.find((column) => column !== x && !column.startsWith("duration")) ??
        numeric[0]);
  return { ...chart.mappings, x, y: y ? [y] : chart.mappings.y };
}

const chartDatasetRoles: Array<{ value: ChartDatasetRole; label: string }> = [
  { value: "fixed", label: "Dataset" },
  { value: "source", label: "Run input data" },
  { value: "signals", label: "Run signals" },
  { value: "portfolio_outputs", label: "Run portfolio series" },
  { value: "portfolio_metrics", label: "Run metrics" },
  { value: "events", label: "Run events" },
  { value: "trials", label: "Optimization trials" },
  { value: "fold_summary", label: "Fold summary" },
];

function chartRoleOptions(type: ChartType): Array<{ value: ChartDatasetRole; label: string }> {
  const allowed: Record<ChartType, ChartDatasetRole[]> = {
    ohlc: ["fixed", "source"],
    timeseries: ["fixed", "source", "portfolio_outputs", "trials", "fold_summary"],
    scatter2d: ["fixed", "source", "portfolio_outputs", "trials", "fold_summary"],
    scatter3d: ["fixed", "source", "portfolio_outputs", "trials"],
    table: ["fixed", "source", "events", "portfolio_outputs", "portfolio_metrics", "trials", "fold_summary"],
    metrics: ["fixed", "portfolio_metrics", "fold_summary"],
    text: ["fixed"],
    calculator: ["fixed", "source"],
  };
  return chartDatasetRoles.filter((role) => allowed[type].includes(role.value));
}

function recordSignature(record: StoreRecord | null | undefined): string {
  if (!record) return "";
  return [
    record.id,
    record.shape.join("x"),
    record.columns.join("|"),
    String(record.attrs.calculator_operation_count ?? ""),
    String(record.attrs.artifact ?? ""),
    JSON.stringify(record.transform ?? null),
  ].join(":");
}

function makeChartId(): string {
  return `chart-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function defaultChartConfig(datasetId: string | null = null): ChartConfig {
  return {
    id: makeChartId(),
    type: "ohlc",
    title: "OHLC",
    datasetId,
    collectionId: null,
    collectionMode: "selected",
    collectionIndex: 0,
    datasetRole: "fixed",
    width: "full",
    height: "normal",
    widthUnits: 12,
    heightPx: 390,
    maxRows: 100000,
    mappings: {
      x: "date",
      open: "open",
      high: "high",
      low: "low",
      close: "close",
      y: ["close"],
    },
  };
}

function defaultFor(schema: JsonSchema): unknown {
  if (schema.default !== undefined) return schema.default;
  if (schema.type === "array") return [];
  if (schema.type === "integer" || schema.type === "number") return 0;
  if (schema.type === "object") {
    return Object.fromEntries(
      Object.entries(schema.properties ?? {}).map(([key, value]) => [key, defaultFor(value)]),
    );
  }
  return "";
}

function displayValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  return String(value ?? "");
}

function defaultsFor(schema?: { properties?: Record<string, JsonSchema> }): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(schema?.properties ?? {})
      .filter(([key]) => key !== "name")
      .map(([key, value]) => [key, defaultFor(value)]),
  );
}

function coerceParam(schema: JsonSchema, value: string): unknown {
  if (schema.type === "array") {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }
  if (schema.type === "integer") return Number.parseInt(value, 10);
  if (schema.type === "number") return Number.parseFloat(value);
  return value;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function PlotlyChart({
  data,
  layout,
}: {
  data: PlotlyTrace[];
  layout: PlotlyLayout;
}) {
  const plotRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!plotRef.current) return;
    Plotly.react(
      plotRef.current,
      data,
      {
        autosize: true,
        margin: { l: 54, r: 28, t: 30, b: 52 },
        paper_bgcolor: "#fbfcfe",
        plot_bgcolor: "#fbfcfe",
        hovermode: "closest",
        dragmode: "zoom",
        legend: {
          orientation: "h",
          x: 0,
          y: 1.12,
          font: { size: 11, color: "#66798f" },
        },
        xaxis: {
          title: { text: "Index / Time" },
          showgrid: true,
          gridcolor: "#edf1f5",
          zeroline: false,
          rangeslider: { visible: false },
        },
        yaxis: {
          title: { text: "Value" },
          showgrid: true,
          gridcolor: "#edf1f5",
          zeroline: false,
        },
        ...layout,
      },
      {
        responsive: true,
        displaylogo: false,
        scrollZoom: true,
      },
    );
    return () => {
      if (plotRef.current) Plotly.purge(plotRef.current);
    };
  }, [data, layout]);

  return <div ref={plotRef} className="plotly-chart" />;
}

function dateAxisOptions(xValues: unknown[], title: string): PlotlyLayout {
  const stringValues = xValues.filter((value): value is string => typeof value === "string");
  const dateLike = stringValues.length > 0 && stringValues.some((value) => !Number.isNaN(Date.parse(value)));
  if (!dateLike) return { title: { text: title } };

  const intraday = stringValues.some((value) => /\d{1,2}:\d{2}/.test(value));
  return {
    title: { text: title },
    type: "date",
    rangebreaks: intraday
      ? [
          { bounds: ["sat", "mon"] },
          { pattern: "hour", bounds: [16, 9.5] },
        ]
      : [{ bounds: ["sat", "mon"] }],
  };
}

function orderedRows(frame: FrameResponse | null, xColumn = "date") {
  const rows = frame?.rows ?? [];
  if (!rows.length || !frame?.columns.includes(xColumn)) return rows;
  if (!rows.some((row) => typeof row[xColumn] === "string" && !Number.isNaN(Date.parse(String(row[xColumn]))))) return rows;
  return [...rows].sort((a, b) => {
    const aTime = Date.parse(String(a[xColumn]));
    const bTime = Date.parse(String(b[xColumn]));
    if (Number.isNaN(aTime) || Number.isNaN(bTime)) return 0;
    return aTime - bTime;
  });
}

function CandleChart({
  frame,
  signalFrame,
  mappings,
}: {
  frame: FrameResponse | null;
  signalFrame: FrameResponse | null;
  mappings?: ChartConfig["mappings"];
}) {
  const rows = frame?.rows ?? [];
  const signals = signalFrame?.rows ?? [];
  const openColumn = mappings?.open ?? "open";
  const highColumn = mappings?.high ?? "high";
  const lowColumn = mappings?.low ?? "low";
  const closeColumn = mappings?.close ?? "close";
  const xColumn = mappings?.x ?? "date";
  const mappedColumns = new Set([xColumn, openColumn, highColumn, lowColumn, closeColumn, "volume"]);
  const overlayColumns =
    (mappings?.y?.length ? mappings.y : frame?.columns ?? [])
      .filter((column) => !mappedColumns.has(column))
      .filter((column) => rows.some((row) => numberValue(row[column]) !== null))
      .slice(0, 5) ?? [];

  const values = rows
    .flatMap((row) => [
      numberValue(row[highColumn]),
      numberValue(row[lowColumn]),
      ...overlayColumns.map((column) => numberValue(row[column])),
    ])
    .filter((value): value is number => value !== null);

  if (
    !frame ||
    rows.length === 0 ||
    values.length === 0 ||
    ![openColumn, highColumn, lowColumn, closeColumn].every((column) => frame.columns.includes(column))
  ) {
    return <div className="empty">Select a dataset with OHLC columns.</div>;
  }

  const ordered = orderedRows(frame, xColumn);
  const xValues = ordered.map((row, index) => row[xColumn] ?? index);
  const traces: PlotlyTrace[] = [
    {
      type: "candlestick",
      name: frame.record.label || frame.record.name,
      x: xValues,
      open: ordered.map((row) => numberValue(row[openColumn])),
      high: ordered.map((row) => numberValue(row[highColumn])),
      low: ordered.map((row) => numberValue(row[lowColumn])),
      close: ordered.map((row) => numberValue(row[closeColumn])),
      increasing: { line: { color: "#2f7d62" }, fillcolor: "#2f7d62" },
      decreasing: { line: { color: "#b54a45" }, fillcolor: "#b54a45" },
    } as PlotlyTrace,
    ...overlayColumns.map((column, index) => ({
      type: "scatter",
      mode: "lines",
      name: column,
      x: xValues,
      y: ordered.map((row) => numberValue(row[column])),
      line: { width: 1.8 },
      opacity: 0.9,
      yaxis: "y",
      legendgroup: "overlay",
      marker: { color: ["#2f6fa3", "#c6792b", "#3b8f66", "#d8524a", "#7353d9"][index % 5] },
    } as PlotlyTrace)),
  ];

  const buySignals = signals
    .map((row, index) => ({ row, index, close: numberValue(rows[index]?.[closeColumn]) }))
    .filter((item) => item.row.action === "buy" && item.close !== null);
  const sellSignals = signals
    .map((row, index) => ({ row, index, close: numberValue(rows[index]?.[closeColumn]) }))
    .filter((item) => item.row.action === "sell" && item.close !== null);
  if (buySignals.length) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Buy",
      x: buySignals.map((item) => xValues[item.index]),
      y: buySignals.map((item) => item.close),
      marker: { symbol: "triangle-up", color: "#2f7d62", size: 10 },
    } as PlotlyTrace);
  }
  if (sellSignals.length) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "Sell",
      x: sellSignals.map((item) => xValues[item.index]),
      y: sellSignals.map((item) => item.close),
      marker: { symbol: "triangle-down", color: "#b54a45", size: 10 },
    } as PlotlyTrace);
  }

  return (
    <PlotlyChart
      data={traces}
      layout={{
        title: { text: frame.record.label || frame.record.name, font: { size: 13, color: "#66798f" } },
        xaxis: { ...dateAxisOptions(xValues, xColumn), rangeslider: { visible: false } },
        yaxis: { title: { text: "Price" } },
      }}
    />
  );
}

function TimeSeriesChart({ frame, mappings }: { frame: FrameResponse | null; mappings: ChartConfig["mappings"] }) {
  const xColumn = mappings.x ?? "date";
  const rows = orderedRows(frame, xColumn);
  const yColumns = (mappings.y ?? []).filter((column) => frame?.columns.includes(column));
  const values = rows
    .flatMap((row) => yColumns.map((column) => numberValue(row[column])))
    .filter((value): value is number => value !== null);

  if (!frame || rows.length === 0 || yColumns.length === 0 || values.length === 0) {
    return <div className="empty">Select numeric columns.</div>;
  }

  const xValues = rows.map((row, index) => row[xColumn] ?? index);

  return (
    <PlotlyChart
      data={yColumns.map((column) => ({
        type: "scatter",
        mode: "lines",
        name: column,
        x: xValues,
        y: rows.map((row) => numberValue(row[column])),
        line: { width: 1.8 },
      } as PlotlyTrace))}
      layout={{
        title: { text: frame.record.label || frame.record.name, font: { size: 13, color: "#66798f" } },
        xaxis: dateAxisOptions(xValues, xColumn),
        yaxis: { title: { text: yColumns.join(", ") || "Value" } },
      }}
    />
  );
}

function CollectionLineChart({
  frames,
  mappings,
  collectionName,
}: {
  frames: FrameResponse[];
  mappings: ChartConfig["mappings"];
  collectionName: string;
}) {
  const yColumns = mappings.y?.length ? mappings.y : [mappings.close ?? "close"];
  const series = frames.flatMap((frame) =>
    yColumns
      .filter((column) => frame.columns.includes(column))
      .map((column) => ({
        name: `${frame.record.label || frame.record.name} · ${column}`,
        frame,
        rows: orderedRows(frame, mappings.x ?? "date"),
        column,
      })),
  );
  const values = series
    .flatMap((item) => item.rows.map((row) => numberValue(row[item.column])))
    .filter((value): value is number => value !== null);

  if (series.length === 0 || values.length === 0) {
    return <div className="empty">No numeric collection members to plot.</div>;
  }

  const shortName = (name: string) =>
    name
      .replace(collectionName, "")
      .replace(/^[-_\s]+/, "")
      .replace(/-prepared$/i, "")
      .replace(/.*(sample[_-]\d+.*fold[_-]\d+.*(?:train|val|test)).*/i, "$1")
      .slice(0, 42);

  return (
    <PlotlyChart
      data={series.map((item) => {
        const xColumn = mappings.x ?? "date";
        return {
          type: "scatter",
          mode: "lines",
          name: shortName(item.name),
          x: item.rows.map((row, index) => row[xColumn] ?? index),
          y: item.rows.map((row) => numberValue(row[item.column])),
          line: { width: 1.5 },
          opacity: 0.82,
        } as PlotlyTrace;
      })}
      layout={{
        title: { text: `${collectionName} · ${frames.length} member(s)`, font: { size: 13, color: "#66798f" } },
        xaxis: dateAxisOptions(series[0]?.rows.map((row, index) => row[mappings.x ?? "date"] ?? index) ?? [], mappings.x ?? "date"),
        yaxis: { title: { text: yColumns.join(", ") || "Value" } },
      }}
    />
  );
}

function Scatter2DChart({ frame, mappings, maxRows }: { frame: FrameResponse | null; mappings: ChartConfig["mappings"]; maxRows?: number }) {
  const xColumn = mappings.x;
  const yColumn = mappings.y?.[0];
  const points =
    frame?.rows
      .map((row) => ({ x: numberValue(row[xColumn ?? ""]), y: numberValue(row[yColumn ?? ""]) }))
      .filter((point): point is { x: number; y: number } => point.x !== null && point.y !== null) ?? [];

  if (!frame || !xColumn || !yColumn || points.length === 0) {
    return <div className="empty">Select X and Y columns.</div>;
  }

  const width = 960;
  const height = 300;
  const pad = 32;
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const sx = (value: number) => pad + ((value - minX) / spanX) * (width - pad * 2);
  const sy = (value: number) => height - pad - ((value - minY) / spanY) * (height - pad * 2);

  return (
    <svg className="chart compact-chart" viewBox={`0 0 ${width} ${height}`} role="img">
      {points.slice(0, maxRows ?? 100000).map((point, index) => (
        <circle key={index} cx={sx(point.x)} cy={sy(point.y)} r="3" className="scatter-point" />
      ))}
      <text x={pad} y={24} className="axis">
        {xColumn} / {yColumn} · {points.length} points
      </text>
    </svg>
  );
}

function Scatter3DChart({ frame, mappings, maxRows }: { frame: FrameResponse | null; mappings: ChartConfig["mappings"]; maxRows?: number }) {
  const xColumn = mappings.x;
  const yColumn = mappings.y?.[0];
  const zColumn = mappings.z;
  const plotRef = React.useRef<HTMLDivElement | null>(null);
  const points =
    frame?.rows
      .map((row) => ({
        x: numberValue(row[xColumn ?? ""]),
        y: numberValue(row[yColumn ?? ""]),
        z: numberValue(row[zColumn ?? ""]),
      }))
      .filter((point): point is { x: number; y: number; z: number } => point.x !== null && point.y !== null && point.z !== null) ??
    [];

  const plottedPoints = useMemo(() => points.slice(0, maxRows ?? 100000), [points, maxRows]);

  useEffect(() => {
    if (!plotRef.current || !frame || !xColumn || !yColumn || !zColumn || plottedPoints.length === 0) return;

    Plotly.react(
      plotRef.current,
      [
        {
          type: "scatter3d",
          mode: "markers",
          x: plottedPoints.map((point) => point.x),
          y: plottedPoints.map((point) => point.y),
          z: plottedPoints.map((point) => point.z),
          marker: {
            size: 3,
            color: plottedPoints.map((point) => point.z),
            colorscale: "Viridis",
            opacity: 0.75,
          },
        },
      ],
      {
        margin: { l: 0, r: 0, t: 28, b: 0 },
        paper_bgcolor: "#fbfcfe",
        plot_bgcolor: "#fbfcfe",
        scene: {
          xaxis: { title: { text: xColumn } },
          yaxis: { title: { text: yColumn } },
          zaxis: { title: { text: zColumn } },
        },
        title: {
          text: `${xColumn} / ${yColumn} / ${zColumn} · ${points.length} points`,
          font: { size: 13, color: "#66798f" },
        },
      },
      {
        responsive: true,
        displaylogo: false,
      },
    );

    return () => {
      if (plotRef.current) Plotly.purge(plotRef.current);
    };
  }, [frame, xColumn, yColumn, zColumn, plottedPoints, points.length]);

  if (!frame || !xColumn || !yColumn || !zColumn || points.length === 0) {
    return <div className="empty">Select X, Y, and Z columns.</div>;
  }

  return <div ref={plotRef} className="plotly-chart" />;
}

function DataTableChart({ frame, mappings, maxRows }: { frame: FrameResponse | null; mappings: ChartConfig["mappings"]; maxRows?: number }) {
  const columns = mappings.y?.length ? mappings.y.filter((column) => frame?.columns.includes(column)) : frame?.columns.slice(0, 8) ?? [];
  if (!frame || columns.length === 0) {
    return <div className="empty">Select table columns.</div>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {frame.rows.slice(0, maxRows ?? 100000).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricsChart({ frame, mappings }: { frame: FrameResponse | null; mappings: ChartConfig["mappings"] }) {
  const row = frame?.rows.at(-1) ?? null;
  const columns = (mappings.y?.length ? mappings.y : frame?.columns ?? [])
    .filter((column) => row && numberValue(row[column]) !== null);

  if (!frame || !row || columns.length === 0) {
    return <div className="empty">Select one or more numeric columns.</div>;
  }

  return (
    <div className="metrics-grid">
      {columns.slice(0, 18).map((column) => {
        const value = numberValue(row[column]);
        return (
          <div className="metric-card" key={column}>
            <span>{column}</span>
            <strong>{value === null ? "-" : Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(4)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function TextArtifactChart({ response }: { response: TextArtifactResponse | null }) {
  if (!response) return <div className="empty">Select a text artifact.</div>;
  return (
    <pre className="text-artifact-viewer">
      {response.text || "(empty text artifact)"}
    </pre>
  );
}

function CalculatorChart({
  chart,
  workspaceId,
  store,
  components,
  onDerived,
  onError,
}: {
  chart: ChartConfig;
  workspaceId: string | null;
  store: StoreSummary | null;
  components: Components;
  onDerived: (sourceId: string, record: StoreRecord, summary: StoreSummary, outputColumns: string[]) => void;
  onError: (message: string) => void;
}) {
  const sourceRecord = store?.records.find((record) => record.id === chart.datasetId) ?? null;
  const sourceColumns = sourceRecord?.columns ?? [];
  const numeric = numericColumns(sourceRecord);
  const technical = components.Technical ?? {};
  const [busy, setBusy] = useState(false);
  const [registeredOpen, setRegisteredOpen] = useState(false);
  const [operation, setOperation] = useState<BasicOperation>("add");
  const [left, setLeft] = useState(numeric[0] ?? "");
  const [rightMode, setRightMode] = useState<"column" | "scalar">("column");
  const [right, setRight] = useState(numeric[1] ?? numeric[0] ?? "");
  const [scalar, setScalar] = useState(1);
  const [scalarText, setScalarText] = useState("1");
  const [windowSize, setWindowSize] = useState(20);
  const [output, setOutput] = useState("calculated");
  const [registeredFunction, setRegisteredFunction] = useState("");
  const [registeredSource, setRegisteredSource] = useState("Internal");
  const [registeredName, setRegisteredName] = useState("Indicator");
  const [editingOperationId, setEditingOperationId] = useState<string | null>(null);
  const registeredSchema = technical[registeredFunction]?.[registeredSource];
  const [registeredParams, setRegisteredParams] = useState<Record<string, unknown>>({});
  const binaryOperation = ["add", "subtract", "multiply", "divide"].includes(operation);
  const windowOperation = ["diff", "pct_change", "rolling_mean", "rolling_std"].includes(operation);
  const operationLabels: Record<BasicOperation, string> = {
    add: "+",
    subtract: "-",
    multiply: "x",
    divide: "/",
    diff: "diff",
    pct_change: "%",
    rolling_mean: "mean",
    rolling_std: "std",
    normalize: "norm",
    zscore: "z",
  };
  const screenExpression = binaryOperation
    ? `${output} = ${left || "col"} ${operationLabels[operation]} ${rightMode === "column" ? right || "col" : scalarText || "0"}`
    : windowOperation
      ? `${output} = ${operationLabels[operation]}(${left || "col"}, ${windowSize})`
      : `${output} = ${operationLabels[operation]}(${left || "col"})`;
  const operationHistory = sourceRecord?.attrs.artifact === "calculator" ? sourceRecord.transform?.operations ?? [] : [];

  useEffect(() => {
    if ((!left || !numeric.includes(left)) && numeric[0]) setLeft(numeric[0]);
    if ((!right || !numeric.includes(right)) && (numeric[1] || numeric[0])) setRight(numeric[1] ?? numeric[0]);
  }, [left, numeric, right]);

  useEffect(() => {
    const names = Object.keys(technical).sort();
    if (!registeredFunction && names[0]) setRegisteredFunction(names[0]);
  }, [registeredFunction, technical]);

  useEffect(() => {
    const sources = Object.keys(technical[registeredFunction] ?? {});
    if (!sources.length) return;
    if (!sources.includes(registeredSource)) setRegisteredSource(sources[0]);
  }, [registeredFunction, registeredSource, technical]);

  useEffect(() => {
    if (!registeredSchema) return;
    const defaults = defaultsFor(registeredSchema);
    setRegisteredParams(defaults);
    const outputNames = defaults.output_names;
    if (outputNames && typeof outputNames === "object") {
      const first = Object.values(outputNames)[0];
      if (typeof first === "string") setRegisteredName(first);
    } else {
      setRegisteredName(String(registeredSchema.properties?.name?.default ?? registeredFunction));
    }
  }, [registeredFunction, registeredSchema, registeredSource]);

  async function runCalculator(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function appendDigit(value: string) {
    setRightMode("scalar");
    setScalarText((current) => {
      const next = current === "0" && value !== "." ? value : `${current}${value}`;
      const parsed = Number.parseFloat(next);
      if (!Number.isNaN(parsed)) setScalar(parsed);
      return next;
    });
  }

  function clearScalar() {
    setScalarText("0");
    setScalar(0);
    setRightMode("scalar");
  }

  function backspaceScalar() {
    setRightMode("scalar");
    setScalarText((current) => {
      const next = current.length > 1 ? current.slice(0, -1) : "0";
      const parsed = Number.parseFloat(next);
      setScalar(Number.isNaN(parsed) ? 0 : parsed);
      return next;
    });
  }

  function chooseOperation(nextOperation: BasicOperation) {
    setOperation(nextOperation);
    if (["add", "subtract", "multiply", "divide"].includes(nextOperation)) setRightMode("scalar");
  }

  function operationSummary(operationItem: CalculatorOperation): string {
    if (operationItem.type === "registered") {
      const transform = operationItem.transforms?.[0];
      const params = transform?.params ?? {};
      const paramText = Object.entries(params)
        .filter(([key]) => !["display", "output_names"].includes(key))
        .map(([key, value]) => `${key}: ${String(value)}`)
        .slice(0, 4)
        .join(", ");
      return `${operationItem.name ?? transform?.name ?? transform?.function ?? "Function"}${paramText ? ` (${paramText})` : ""}`;
    }
    const op = operationItem.operation ?? "add";
    const rhs = operationItem.right ?? operationItem.scalar ?? "";
    const detail = ["diff", "pct_change", "rolling_mean", "rolling_std"].includes(op)
      ? `${operationItem.left}, window ${operationItem.window ?? 1}`
      : `${operationItem.left} ${operationLabels[op]} ${rhs}`;
    return `${operationItem.output ?? op} = ${detail}`;
  }

  function editOperation(operationItem: CalculatorOperation) {
    setEditingOperationId(operationItem.id ?? null);
    if (operationItem.type === "basic") {
      const nextOperation = operationItem.operation ?? "add";
      setOperation(nextOperation);
      setLeft(operationItem.left ?? numeric[0] ?? "");
      setRight(operationItem.right ?? numeric[1] ?? numeric[0] ?? "");
      setOutput(operationItem.output ?? "calculated");
      setWindowSize(Number(operationItem.window ?? 20));
      if (operationItem.scalar !== null && operationItem.scalar !== undefined) {
        setRightMode("scalar");
        setScalar(Number(operationItem.scalar));
        setScalarText(String(operationItem.scalar));
      } else {
        setRightMode("column");
      }
      return;
    }
    const transform = operationItem.transforms?.[0];
    if (transform) {
      setRegisteredFunction(transform.function);
      setRegisteredSource(transform.source);
      setRegisteredName(operationItem.name ?? transform.name ?? transform.function);
      setRegisteredParams(transform.params ?? {});
      setRegisteredOpen(true);
    }
  }

  async function deleteOperation(operationId?: string) {
    if (!workspaceId || !sourceRecord || !operationId) return;
    await runCalculator(async () => {
      const result = await api<{ store: StoreSummary; record: StoreRecord }>(
        `/workspaces/${workspaceId}/calculator/${sourceRecord.id}/operations/${operationId}`,
        { method: "DELETE" },
      );
      onDerived(sourceRecord.id, result.record, result.store, result.record.columns);
      if (editingOperationId === operationId) setEditingOperationId(null);
    });
  }

  function updateRegisteredParam(key: string, value: unknown) {
    setRegisteredParams((current) => ({ ...current, [key]: value }));
  }

  function setRegisteredOutput(outputKey: string, value: string) {
    setRegisteredParams((current) => ({
      ...current,
      output_names: { ...((current.output_names as Record<string, string>) ?? {}), [outputKey]: value },
    }));
  }

  const runBasic = () =>
    runCalculator(async () => {
      if (!workspaceId || !sourceRecord) return;
      const payload = {
        operation,
        left,
        right: binaryOperation && rightMode === "column" ? right : null,
        scalar: binaryOperation && rightMode === "scalar" ? scalar : null,
        window: windowOperation ? windowSize : null,
        output,
      };
      if (editingOperationId) {
        const result = await api<{ store: StoreSummary; record: StoreRecord }>(
          `/workspaces/${workspaceId}/calculator/${sourceRecord.id}/operations/${editingOperationId}`,
          {
            method: "PATCH",
            body: JSON.stringify({ operation: payload }),
          },
        );
        setEditingOperationId(null);
        onDerived(sourceRecord.id, result.record, result.store, [output]);
        return;
      }
      const result = await api<{ store: StoreSummary; record: StoreRecord }>(`/workspaces/${workspaceId}/calculator/basic`, {
        method: "POST",
        body: JSON.stringify({
          dataset_id: sourceRecord.id,
          ...payload,
          name: `${sourceRecord.name}-${output}`,
        }),
      });
      onDerived(sourceRecord.id, result.record, result.store, [output]);
    });

  const runRegistered = () =>
    runCalculator(async () => {
      if (!workspaceId || !sourceRecord) return;
      const registeredOperation = {
        type: "registered",
        name: registeredName,
        transforms: [
          {
            category: "Technical",
            function: registeredFunction,
            source: registeredSource,
            name: registeredName,
            params: registeredParams,
          },
        ],
      };
      if (editingOperationId) {
        const result = await api<{ store: StoreSummary; record: StoreRecord }>(
          `/workspaces/${workspaceId}/calculator/${sourceRecord.id}/operations/${editingOperationId}`,
          {
            method: "PATCH",
            body: JSON.stringify({ operation: registeredOperation }),
          },
        );
        setEditingOperationId(null);
        onDerived(sourceRecord.id, result.record, result.store, result.record.columns);
        setRegisteredOpen(false);
        return;
      }
      await api(`/workspaces/${workspaceId}/calculator/transforms`, {
        method: "POST",
        body: JSON.stringify({
          function: registeredFunction,
          source: registeredSource,
          name: registeredName,
          params: registeredParams,
        }),
      });
      const result = await api<{ store: StoreSummary; record: StoreRecord }>(`/workspaces/${workspaceId}/calculator/derive`, {
        method: "POST",
        body: JSON.stringify({ dataset_id: sourceRecord.id, name: `${sourceRecord.name}-${registeredName}` }),
      });
      onDerived(
        sourceRecord.id,
        result.record,
        result.store,
        Object.values((registeredParams.output_names as Record<string, string>) ?? {}).filter(Boolean),
      );
      setRegisteredOpen(false);
    });

  if (!sourceRecord) {
    return <div className="empty">Select a source dataset in calculator settings.</div>;
  }

  return (
    <div className="calculator-pane">
      <div className="calculator-display">
        <span>{sourceRecord.label || sourceRecord.name}</span>
        <strong>{screenExpression}</strong>
      </div>
      <div className="calculator-body">
        <div className="calculator-controls">
          <label className="field">
            <span>Output</span>
            <input value={output} onChange={(event) => setOutput(event.target.value)} />
          </label>
        <label className="field">
          <span>Left</span>
          <select value={left} onChange={(event) => setLeft(event.target.value)}>
            {numeric.map((column) => (
              <option key={column}>{column}</option>
            ))}
          </select>
        </label>
        {binaryOperation && (
          <>
            <label className="field">
              <span>Right Type</span>
              <select value={rightMode} onChange={(event) => setRightMode(event.target.value as "column" | "scalar")}>
                <option value="column">Column</option>
                <option value="scalar">Scalar</option>
              </select>
            </label>
            {rightMode === "column" ? (
              <label className="field">
                <span>Right</span>
                <select value={right} onChange={(event) => setRight(event.target.value)}>
                  {numeric.map((column) => (
                    <option key={column}>{column}</option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="field">
                <span>Scalar</span>
                <input
                  type="number"
                  value={scalarText}
                  onChange={(event) => {
                    setScalarText(event.target.value);
                    setScalar(Number.parseFloat(event.target.value) || 0);
                  }}
                />
              </label>
            )}
          </>
        )}
        {windowOperation && (
          <label className="field">
            <span>Window</span>
            <input type="number" min="1" value={windowSize} onChange={(event) => setWindowSize(Number.parseInt(event.target.value, 10) || 1)} />
          </label>
        )}
      </div>
        <div className="calculator-pad" aria-label="Calculator buttons">
          <button className={operation === "add" ? "active" : ""} onClick={() => chooseOperation("add")}>+</button>
          <button className={operation === "subtract" ? "active" : ""} onClick={() => chooseOperation("subtract")}>-</button>
          <button className={operation === "multiply" ? "active" : ""} onClick={() => chooseOperation("multiply")}>x</button>
          <button className={operation === "divide" ? "active" : ""} onClick={() => chooseOperation("divide")}>/</button>
          {["7", "8", "9"].map((value) => <button key={value} onClick={() => appendDigit(value)}>{value}</button>)}
          <button className={operation === "diff" ? "active transform-key" : "transform-key"} onClick={() => chooseOperation("diff")}>diff</button>
          {["4", "5", "6"].map((value) => <button key={value} onClick={() => appendDigit(value)}>{value}</button>)}
          <button className={operation === "pct_change" ? "active transform-key" : "transform-key"} onClick={() => chooseOperation("pct_change")}>pct</button>
          {["1", "2", "3"].map((value) => <button key={value} onClick={() => appendDigit(value)}>{value}</button>)}
          <button className={operation === "rolling_mean" ? "active transform-key" : "transform-key"} onClick={() => chooseOperation("rolling_mean")}>mean</button>
          <button onClick={clearScalar}>C</button>
          <button onClick={() => appendDigit("0")}>0</button>
          <button onClick={() => appendDigit(".")}>.</button>
          <button className={operation === "rolling_std" ? "active transform-key" : "transform-key"} onClick={() => chooseOperation("rolling_std")}>std</button>
          <button onClick={backspaceScalar}>del</button>
          <button className={operation === "normalize" ? "active transform-key" : "transform-key"} onClick={() => chooseOperation("normalize")}>norm</button>
          <button className={operation === "zscore" ? "active transform-key" : "transform-key"} onClick={() => chooseOperation("zscore")}>z</button>
          <button className="function-key" disabled={busy} onClick={() => setRegisteredOpen(true)}>fn</button>
        </div>
      </div>
      <div className="calculator-keys">
        <button disabled={busy || !left || !output} onClick={runBasic}>
          <Calculator size={16} /> {editingOperationId ? "Update" : "Apply"}
        </button>
        <button disabled={busy} onClick={() => setRegisteredOpen(true)}>
          <Sparkles size={16} /> Functions
        </button>
        {editingOperationId && (
          <button onClick={() => setEditingOperationId(null)}>
            Cancel Edit
          </button>
        )}
      </div>
      <div className="calculator-history">
        <div className="calculator-history-header">
          <strong>Recipe</strong>
          <span>{operationHistory.length} operation(s)</span>
        </div>
        {operationHistory.length === 0 ? (
          <div className="empty compact-empty">No calculator operations yet.</div>
        ) : (
          operationHistory.map((operationItem, index) => (
            <div className={editingOperationId === operationItem.id ? "operation-row active" : "operation-row"} key={operationItem.id ?? index}>
              <div>
                <strong>{index + 1}. {operationItem.type === "registered" ? "Function" : "Math"}</strong>
                <span>{operationSummary(operationItem)}</span>
              </div>
              <div className="operation-actions">
                <button onClick={() => editOperation(operationItem)}>Edit</button>
                <button className="danger-button" onClick={() => deleteOperation(operationItem.id)}>Delete</button>
              </div>
            </div>
          ))
        )}
      </div>
      {registeredOpen && (
        <div className="modal-backdrop nested" onMouseDown={() => setRegisteredOpen(false)}>
          <div className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <strong>Registered Function</strong>
                <span>Derive from {sourceRecord.label || sourceRecord.name}</span>
              </div>
              <button className="icon-button" onClick={() => setRegisteredOpen(false)}>
                x
              </button>
            </div>
            <div className="modal-body">
              <label className="field">
                <span>Function</span>
                <select value={registeredFunction} onChange={(event) => setRegisteredFunction(event.target.value)}>
                  {Object.keys(technical).sort().map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Source</span>
                <select value={registeredSource} onChange={(event) => setRegisteredSource(event.target.value)}>
                  {Object.keys(technical[registeredFunction] ?? {}).map((source) => (
                    <option key={source}>{source}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Transform Name</span>
                <input value={registeredName} onChange={(event) => setRegisteredName(event.target.value)} />
              </label>
              {Object.entries(registeredSchema?.properties ?? {})
                .filter(([key]) => !["name", "output_names", "display"].includes(key))
                .slice(0, 10)
                .map(([key, schema]) => (
                  <label className="field" key={key}>
                    <span>{key}</span>
                    {(schema.use_variable_options || ["real", "open", "high", "low", "close"].includes(key)) && sourceColumns.length ? (
                      <select value={String(registeredParams[key] ?? schema.default ?? "")} onChange={(event) => updateRegisteredParam(key, event.target.value)}>
                        {sourceColumns.map((column) => (
                          <option key={column}>{column}</option>
                        ))}
                      </select>
                    ) : schema.enum ? (
                      <select value={String(registeredParams[key] ?? "")} onChange={(event) => updateRegisteredParam(key, coerceParam(schema, event.target.value))}>
                        {schema.enum.map((option) => (
                          <option key={String(option)} value={String(option)}>
                            {String(option)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        value={displayValue(registeredParams[key])}
                        type={schema.type === "integer" || schema.type === "number" ? "number" : "text"}
                        onChange={(event) => updateRegisteredParam(key, coerceParam(schema, event.target.value))}
                      />
                    )}
                  </label>
                ))}
              {Object.keys((registeredParams.output_names as Record<string, string>) ?? {}).map((key) => (
                <label className="field" key={key}>
                  <span>Output {key}</span>
                  <input
                    value={String((registeredParams.output_names as Record<string, string>)[key])}
                    onChange={(event) => setRegisteredOutput(key, event.target.value)}
                  />
                </label>
              ))}
              <button disabled={busy || !registeredFunction} onClick={runRegistered}>
                <Sparkles size={16} /> Derive Function
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ChartWidget({
  chart,
  workspaceId,
  store,
  components,
  signalFrame,
  activeFold,
  activeSplit,
  dragging,
  onDerived,
  onError,
  onConfigure,
  onResize,
  onDragStart,
  onDragOver,
  onDragEnter,
  onDrop,
  onRemove,
}: {
  chart: ChartConfig;
  workspaceId: string | null;
  store: StoreSummary | null;
  components: Components;
  signalFrame: FrameResponse | null;
  activeFold: string;
  activeSplit: string;
  dragging: boolean;
  onDerived: (sourceId: string, record: StoreRecord, summary: StoreSummary, outputColumns: string[]) => void;
  onError: (message: string) => void;
  onConfigure: (id: string) => void;
  onResize: (id: string, size: Partial<Pick<ChartConfig, "widthUnits" | "heightPx" | "width" | "height">>) => void;
  onDragStart: (id: string) => void;
  onDragOver: (event: React.DragEvent<HTMLDivElement>) => void;
  onDragEnter: (id: string) => void;
  onDrop: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  const [chartFrame, setChartFrame] = useState<FrameResponse | null>(null);
  const [collectionFrames, setCollectionFrames] = useState<FrameResponse[]>([]);
  const [chartSignalFrame, setChartSignalFrame] = useState<FrameResponse | null>(null);
  const [textArtifact, setTextArtifact] = useState<TextArtifactResponse | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [resizeStart, setResizeStart] = useState<{
    x: number;
    y: number;
    widthUnits: number;
    heightPx: number;
  } | null>(null);
  const chartCollection = store?.artifacts?.find((artifact) => artifact.id === chart.collectionId && artifact.artifact_type === "collection") ?? null;
  const chartLeaves = filterCollectionLeaves(collectionLeafRecordsFromStore(store, chartCollection), activeFold, activeSplit);
  const chartCollectionIndex = Math.min(Math.max(chart.collectionIndex ?? 0, 0), Math.max(chartLeaves.length - 1, 0));
  const activeChartDatasetId = chart.collectionId ? chartLeaves[chartCollectionIndex]?.record.id ?? null : chart.datasetId;
  const collectionSignature = chartLeaves.map((leaf) => recordSignature(leaf.record)).join("::");
  const chartRecordSignature = recordSignature(store?.records.find((record) => record.id === activeChartDatasetId));
  const signalRecordSignature = recordSignature(store?.records.find((record) => record.id === chart.signalDatasetId));
  const artifactSignature = JSON.stringify(store?.artifacts?.find((artifact) => artifact.id === chart.artifactId) ?? null);

  useEffect(() => {
    if (chart.type === "text") {
      setChartFrame(null);
      return;
    }
    if (!workspaceId || !activeChartDatasetId) {
      setChartFrame(null);
      return;
    }
    api<FrameResponse>(`/workspaces/${workspaceId}/records/${activeChartDatasetId}/frame?limit=${chart.maxRows ?? 100000}`)
      .then((nextFrame) => {
        setChartFrame(nextFrame);
        setChartError(null);
      })
      .catch((err) => setChartError(err instanceof Error ? err.message : String(err)));
  }, [workspaceId, chart.type, activeChartDatasetId, chart.maxRows, chartRecordSignature]);

  useEffect(() => {
    if (!workspaceId || !chart.collectionId || chart.collectionMode !== "all" || chart.type === "text" || chart.type === "calculator") {
      setCollectionFrames([]);
      return;
    }
    Promise.all(
      chartLeaves.slice(0, 60).map((leaf) =>
        api<FrameResponse>(`/workspaces/${workspaceId}/records/${leaf.record.id}/frame?limit=${chart.maxRows ?? 100000}`),
      ),
    )
      .then((frames) => {
        setCollectionFrames(frames);
        setChartError(null);
      })
      .catch((err) => setChartError(err instanceof Error ? err.message : String(err)));
  }, [workspaceId, chart.collectionId, chart.collectionMode, chart.type, chart.maxRows, collectionSignature]);

  useEffect(() => {
    if (chart.type !== "text") {
      setTextArtifact(null);
      return;
    }
    if (!workspaceId || !chart.artifactId) {
      setTextArtifact(null);
      return;
    }
    api<TextArtifactResponse>(`/workspaces/${workspaceId}/artifacts/${chart.artifactId}/text`)
      .then((nextArtifact) => {
        setTextArtifact(nextArtifact);
        setChartError(null);
      })
      .catch((err) => setChartError(err instanceof Error ? err.message : String(err)));
  }, [workspaceId, chart.type, chart.artifactId, artifactSignature]);

  useEffect(() => {
    if (!workspaceId || !chart.signalDatasetId) {
      setChartSignalFrame(null);
      return;
    }
    api<FrameResponse>(`/workspaces/${workspaceId}/records/${chart.signalDatasetId}/frame?limit=${chart.maxRows ?? 100000}`)
      .then((nextFrame) => setChartSignalFrame(nextFrame))
      .catch((err) => setChartError(err instanceof Error ? err.message : String(err)));
  }, [workspaceId, chart.signalDatasetId, chart.maxRows, signalRecordSignature]);

  useEffect(() => {
    if (!resizeStart) return;
    const start = resizeStart;

    function onMove(event: MouseEvent) {
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      const nextWidthUnits = Math.max(3, Math.min(12, start.widthUnits + Math.round(dx / 70)));
      const nextHeightPx = Math.max(220, Math.min(900, start.heightPx + dy));
      onResize(chart.id, {
        widthUnits: nextWidthUnits,
        heightPx: nextHeightPx,
        width: nextWidthUnits >= 12 ? "full" : nextWidthUnits >= 8 ? "wide" : "normal",
        height: nextHeightPx >= 500 ? "tall" : "normal",
      });
    }

    function onUp() {
      setResizeStart(null);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [chart.id, onResize, resizeStart]);

  const effectiveMappings = mappingsForFrame(chart, chartFrame);
  let body: React.ReactNode;
  if (chartError) {
    body = <div className="empty">{chartError}</div>;
  } else if (chart.type === "calculator") {
    body = (
      <CalculatorChart
        chart={chart}
        workspaceId={workspaceId}
        store={store}
        components={components}
        onDerived={onDerived}
        onError={onError}
      />
    );
  } else if (chart.collectionId && chart.collectionMode === "all" && (chart.type === "ohlc" || chart.type === "timeseries")) {
    body = <CollectionLineChart frames={collectionFrames} mappings={effectiveMappings} collectionName={chartCollection?.name ?? "Collection"} />;
  } else if (chart.type === "ohlc") {
    body = <CandleChart frame={chartFrame} signalFrame={chartSignalFrame ?? signalFrame} mappings={effectiveMappings} />;
  } else if (chart.type === "timeseries") {
    body = <TimeSeriesChart frame={chartFrame} mappings={effectiveMappings} />;
  } else if (chart.type === "scatter2d") {
    body = <Scatter2DChart frame={chartFrame} mappings={effectiveMappings} maxRows={chart.maxRows} />;
  } else if (chart.type === "scatter3d") {
    body = <Scatter3DChart frame={chartFrame} mappings={effectiveMappings} maxRows={chart.maxRows} />;
  } else if (chart.type === "metrics") {
    body = <MetricsChart frame={chartFrame} mappings={effectiveMappings} />;
  } else if (chart.type === "text") {
    body = <TextArtifactChart response={textArtifact} />;
  } else {
    body = <DataTableChart frame={chartFrame} mappings={effectiveMappings} maxRows={chart.maxRows} />;
  }

  return (
    <div
      className={[
        "chart-card",
        `chart-width-${chart.width ?? "normal"}`,
        `chart-height-${chart.height ?? "normal"}`,
        dragging ? "dragging" : "",
      ].join(" ")}
      style={{
        gridColumn: chart.widthUnits ? `span ${chart.widthUnits}` : undefined,
        "--chart-height": `${chart.heightPx ?? ((chart.height ?? "normal") === "tall" ? 520 : 390)}px`,
      } as React.CSSProperties}
      onDragOver={onDragOver}
      onDragEnter={() => onDragEnter(chart.id)}
      onDrop={() => onDrop(chart.id)}
    >
      <div className="chart-card-header">
        <button
          className="icon-button drag-handle"
          title="Move chart"
          aria-label="Move chart"
          draggable
          onDragStart={(event) => {
            event.dataTransfer.effectAllowed = "move";
            onDragStart(chart.id);
          }}
        >
          <GripVertical size={15} />
        </button>
        <div>
          <strong>{chart.title}</strong>
          <span>
            {chart.type === "text"
              ? textArtifact?.artifact.name ?? "No text artifact"
              : chart.collectionId
                ? `${chartCollection?.name ?? "Collection"}${chart.collectionMode === "all" ? " · all" : ` · ${chartLeaves[chartCollectionIndex]?.label ?? "member"}`}`
                : chartFrame?.record.name ?? "No dataset"}
          </span>
        </div>
        <div className="chart-actions">
          <button className="icon-button" title="Configure chart" onClick={() => onConfigure(chart.id)}>
            <SlidersHorizontal size={15} />
          </button>
          <button className="icon-button" title="Remove chart" onClick={() => onRemove(chart.id)}>
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      {body}
      <div
        className="resize-grip"
        title="Resize chart"
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setResizeStart({
            x: event.clientX,
            y: event.clientY,
            widthUnits: chart.widthUnits ?? (chart.width === "full" ? 12 : chart.width === "wide" ? 8 : 6),
            heightPx: chart.heightPx ?? ((chart.height ?? "normal") === "tall" ? 520 : 390),
          });
        }}
      />
    </div>
  );
}

function App() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [activePage, setActivePage] = useState("data");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [layoutDialogOpen, setLayoutDialogOpen] = useState(false);
  const [dataStoreOpen, setDataStoreOpen] = useState(false);
  const [components, setComponents] = useState<Components>({});
  const [executors, setExecutors] = useState<Executors>({});
  const [evaluators, setEvaluators] = useState<Evaluators>({});
  const [store, setStore] = useState<StoreSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [frame, setFrame] = useState<FrameResponse | null>(null);
  const [signalFrame, setSignalFrame] = useState<FrameResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [providerKey, setProviderKey] = useState(() => localStorage.getItem("quantapy.fmpKey") ?? "");
  const [dataCategory, setDataCategory] = useState("Market");
  const [dataFunction, setDataFunction] = useState("OHLC");
  const [dataSource, setDataSource] = useState("FMP");
  const [dataParams, setDataParams] = useState<Record<string, unknown>>({
    source_ids: ["AAPL"],
    interval: "1hour",
    date_range: "3mo",
    from_date: "",
    to_date: "",
    limit: 0,
  });
  const [prepareSourceId, setPrepareSourceId] = useState("");
  const [workingCollectionId, setWorkingCollectionId] = useState("");
  const [noiseCount, setNoiseCount] = useState(5);
  const [noiseStddev, setNoiseStddev] = useState(0.01);
  const [splitMethod, setSplitMethod] = useState("holdout");
  const [splitTrainRatio, setSplitTrainRatio] = useState(0.7);
  const [splitValRatio, setSplitValRatio] = useState(0.15);
  const [splitTestRatio, setSplitTestRatio] = useState(0.15);
  const [splitFolds, setSplitFolds] = useState(3);
  const [prepareRecipeId, setPrepareRecipeId] = useState("");
  const [indicatorFunction, setIndicatorFunction] = useState("Moving Average");
  const [indicatorSource, setIndicatorSource] = useState("Internal");
  const [indicatorName, setIndicatorName] = useState("Leading");
  const [indicatorParams, setIndicatorParams] = useState<Record<string, unknown>>({
    timeperiod: 20,
    real: "close",
    output_names: { output: "Leading" },
    display: "Overlay",
  });
  const [transformDatasetId, setTransformDatasetId] = useState<string>("");
  const [backtestDatasetId, setBacktestDatasetId] = useState<string>("");
  const [optimizeDatasetId, setOptimizeDatasetId] = useState<string>("");
  const [signalFunction, setSignalFunction] = useState("Crossover");
  const [signalSource, setSignalSource] = useState("Internal");
  const [signalParams, setSignalParams] = useState<Record<string, unknown>>({
    value1: "Leading",
    value2: "Lagging",
    action: "enter",
    direction: "long",
  });
  const [orderFunction, setOrderFunction] = useState("Market");
  const [orderSource, setOrderSource] = useState("Internal");
  const [orderParams, setOrderParams] = useState<Record<string, unknown>>({
    on_signal: "entry",
    on_price: "close",
    on_bar: "current",
  });
  const [strategyName, setStrategyName] = useState("Strategy");
  const [strategySignals, setStrategySignals] = useState<ComponentSpec[]>([]);
  const [strategyOrders, setStrategyOrders] = useState<ComponentSpec[]>([]);
  const [strategyComponentCategory, setStrategyComponentCategory] = useState("Signal");
  const [selectedRunner, setSelectedRunner] = useState("trading.backtest");
  const [executorConfig, setExecutorConfig] = useState<Record<string, unknown>>({});
  const [selectedEvaluator, setSelectedEvaluator] = useState("trading.portfolio_metrics");
  const [evaluatorConfig, setEvaluatorConfig] = useState<Record<string, unknown>>({});
  const [templateSections, setTemplateSections] = useState<Record<string, TemplateSectionState>>({});
  const [simulationFunction, setSimulationFunction] = useState("Backtest");
  const [simulationSource, setSimulationSource] = useState("Internal");
  const [simulationParams, setSimulationParams] = useState<Record<string, unknown>>({
    initial_investment: 10000,
    close_on_completion: "close",
  });
  const [optParams, setOptParams] = useState([
    { target: "Transform", name: "Leading", index: "", param: "timeperiod", dtype: "integer", low: 5, high: 40 },
    { target: "Transform", name: "Lagging", index: "", param: "timeperiod", dtype: "integer", low: 20, high: 120 },
  ]);
  const [newOptParam, setNewOptParam] = useState({
    target: "Transform",
    name: "",
    index: "",
    param: "timeperiod",
    dtype: "integer",
    low: 1,
    high: 100,
  });
  const [optimizationTrials, setOptimizationTrials] = useState(25);
  const [optimizationObjectives, setOptimizationObjectives] = useState("Maximize Profit, Maximize Sharpe Ratio");
  const [validationFunction, setValidationFunction] = useState("Holdout");
  const [validationSource, setValidationSource] = useState("Internal");
  const [validationParams, setValidationParams] = useState<Record<string, unknown>>({ train_ratio: 0.75 });
  const [bestTrialFunction, setBestTrialFunction] = useState("Distance from Ideal");
  const [bestTrialSource, setBestTrialSource] = useState("Internal");
  const [bestTrialParams, setBestTrialParams] = useState<Record<string, unknown>>({});
  const [optimizerFunction, setOptimizerFunction] = useState("Bayesian");
  const [optimizerSource, setOptimizerSource] = useState("Internal");
  const [charts, setCharts] = useState<ChartConfig[]>(() => {
    const saved = localStorage.getItem("quantapy.activeLayout");
    if (saved) {
      try {
        const layout = JSON.parse(saved) as DashboardLayout;
        if (Array.isArray(layout.charts)) return layout.charts;
      } catch {
        return [defaultChartConfig()];
      }
    }
    return [defaultChartConfig()];
  });
  const [layoutName, setLayoutName] = useState("Research Layout");
  const [savedLayouts, setSavedLayouts] = useState<DashboardLayout[]>(() => {
    const saved = localStorage.getItem("quantapy.savedLayouts");
    if (!saved) return [];
    try {
      const layouts = JSON.parse(saved) as DashboardLayout[];
      return Array.isArray(layouts) ? layouts : [];
    } catch {
      return [];
    }
  });
  const [activeRunId, setActiveRunId] = useState<string>("");
  const [activeFold, setActiveFold] = useState<string>("all");
  const [activeSplit, setActiveSplit] = useState<string>("test");
  const [editingChartId, setEditingChartId] = useState<string | null>(null);
  const [draggingChartId, setDraggingChartId] = useState<string | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>("");
  const lastChartAdd = useRef<{ key: string; at: number } | null>(null);

  const selected = store?.records.find((record) => record.id === selectedId) ?? null;
  const selectedRecordSignature = recordSignature(selected);
  const rawRecord =
    (selected?.kind === "raw" ? selected : null) ??
    [...(store?.records ?? [])].reverse().find((record) => record.kind === "raw") ??
    null;
  const transformSourceRecord =
    store?.records.find((record) => record.id === transformDatasetId) ??
    rawRecord;
  const transformSourceColumns = transformSourceRecord?.columns ?? [];
  const indicatorRecord =
    (selected?.kind === "derived" && ["calculator", "indicators"].includes(String(selected.attrs.artifact)) ? selected : null) ??
    [...(store?.records ?? [])].reverse().find((record) => record.kind === "derived" && ["calculator", "indicators"].includes(String(record.attrs.artifact))) ??
    null;
  const fallbackBacktestRecord =
    store?.records.find((record) => record.id === backtestDatasetId) ??
    indicatorRecord;
  const fallbackOptimizeRecord =
    store?.records.find((record) => record.id === optimizeDatasetId) ??
    rawRecord;
  const ohlcLikeRecords = (store?.records ?? []).filter((record) =>
    ["raw", "derived"].includes(record.kind) && ["open", "high", "low", "close"].every((column) => record.columns.includes(column)),
  );
  const indicatorLikeRecords = ohlcLikeRecords.filter((record) =>
    record.kind === "derived" || record.columns.some((column) => !["date", "open", "high", "low", "close", "volume"].includes(column)),
  );
  const latestBacktest = [...(store?.records ?? [])].reverse().find((record) => record.kind === "backtest");
  const latestPortfolioMetrics = [...(store?.records ?? [])].reverse().find((record) => record.attrs.artifact === "portfolio_metrics");
  const grouped = store?.grouped ?? {};
  const navigation = store?.navigation ?? [];
  const visibleRecords = store?.visible_records ?? store?.records ?? [];
  const allArtifacts = store?.artifacts ?? [];
  const memberDatasetIds = useMemo(() => collectionMemberDatasetIds(allArtifacts), [allArtifacts]);
  const memberArtifactIds = useMemo(() => collectionMemberArtifactIds(allArtifacts), [allArtifacts]);
  const collectionArtifacts = allArtifacts.filter((artifact) => artifact.artifact_type === "collection" && !memberArtifactIds.has(artifact.id));
  const topLevelNavigation = useMemo(() => filterMemberNodes(navigation, memberDatasetIds), [navigation, memberDatasetIds]);
  const topLevelRecords = visibleRecords.filter((record) => !memberDatasetIds.has(record.id));
  const topLevelFileArtifacts = allArtifacts.filter((artifact) => artifact.artifact_type !== "collection" && !memberArtifactIds.has(artifact.id));
  const selectedCollection = collectionArtifacts.find((artifact) => artifact.id === selectedCollectionId) ?? collectionArtifacts.at(-1) ?? null;
  const configuredWorkingCollection =
    collectionArtifacts.find((artifact) => artifact.id === workingCollectionId) ??
    selectedCollection ??
    collectionArtifacts.at(-1) ??
    null;
  const configuredWorkingLeaves = configuredWorkingCollection
    ? filterCollectionLeaves(collectionLeafRecordsFromStore(store, configuredWorkingCollection), activeFold, activeSplit)
    : [];
  const configuredWorkingFallbackLeaves = configuredWorkingCollection ? collectionLeafRecordsFromStore(store, configuredWorkingCollection) : [];
  const activeWorkingRecord =
    configuredWorkingLeaves[0]?.record ??
    configuredWorkingFallbackLeaves[0]?.record ??
    null;
  const backtestDatasetRecord = activeWorkingRecord ?? fallbackBacktestRecord;
  const optimizeDatasetRecord = activeWorkingRecord ?? fallbackOptimizeRecord;
  const backtestSignalColumns = numericColumns(backtestDatasetRecord).filter(
    (column) => !["open", "high", "low", "close", "volume"].includes(column),
  );
  const backtestNumericColumns = numericColumns(backtestDatasetRecord);
  const backtestColumnOptions = backtestNumericColumns.length ? backtestNumericColumns : backtestDatasetRecord?.columns ?? [];
  const optimizeRecipeTransforms = useMemo(
    () =>
      ((optimizeDatasetRecord?.transform?.operations ?? []) as CalculatorOperation[])
        .filter((operation) => operation.type === "registered")
        .flatMap((operation) =>
          (operation.transforms ?? []).map((transform) => ({
            name: transform.name || operation.name || transform.function,
            function: transform.function,
            params: transform.params ?? {},
          })),
        )
        .filter((transform) => Boolean(transform.name)),
    [optimizeDatasetRecord?.transform],
  );
  const chartContextCollection =
    collectionArtifacts.find((artifact) => charts.some((chart) => chart.collectionId === artifact.id)) ??
    selectedCollection;
  const chartContextLeaves = collectionLeafRecords(chartContextCollection);
  const collectionFoldOptions = useMemo(
    () => Array.from(new Set(chartContextLeaves.map(leafFold).filter((fold): fold is string => Boolean(fold)))).sort((a, b) => Number(a) - Number(b)),
    [chartContextLeaves],
  );
  const collectionSplitOptions = useMemo(
    () => {
      const detected = Array.from(new Set(chartContextLeaves.map(leafSplit).filter((split): split is string => Boolean(split))));
      const order = ["train", "val", "test"];
      return detected.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    },
    [chartContextLeaves],
  );
  const prepareSourceOptions = useMemo(
    () => [
      ...topLevelRecords.map((record) => ({
        id: record.id,
        label: record.label || record.name,
        detail: `${record.kind} · ${record.shape[0]} x ${record.shape[1]}`,
      })),
      ...collectionArtifacts.map((artifact) => ({
        id: artifact.id,
        label: `Collection: ${artifact.name}`,
        detail: `${artifact.role} · ${Number((artifact.metadata.members as unknown[])?.length ?? 0)} member(s)`,
      })),
    ],
    [topLevelRecords, collectionArtifacts],
  );
  const calculatorRecipeRecords = visibleRecords.filter((record) => artifactOf(record) === "calculator");
  const studyRuns = store?.study_runs ?? [];
  const workspaceModel = store?.workspace;
  const activeRun = studyRuns.find((run) => run.run_id === activeRunId) ?? null;
  const contextFoldOptions = activeRun ? activeRun.folds.map((fold) => String(fold)) : collectionFoldOptions;
  const contextSplitOptions = activeRun ? ["train", "test"] : (collectionSplitOptions.length ? collectionSplitOptions : ["train", "val", "test"]);
  const hasCollectionContext = Boolean(chartContextCollection && chartContextLeaves.length);
  const activeExecutionRun = workspaceModel?.executions?.runs.find((run) => run.id === activeRunId) ?? null;
  const activeRunRecords =
    activeRun?.artifacts?.length
      ? activeRun.artifacts
      : activeExecutionRun
        ? (store?.records ?? []).filter((record) =>
            [...activeExecutionRun.input_ids, ...activeExecutionRun.output_ids].includes(record.id) ||
            record.attrs.source_run_id === activeRunId
          )
        : (store?.records ?? []).filter((record) => activeRunId && record.run_id === activeRunId);
  const dataComponents = components[dataCategory] ?? {};
  const dataSchema = dataComponents[dataFunction]?.[dataSource];
  const dataFunctionOptions = useMemo(() => Object.keys(dataComponents).sort(), [dataComponents]);
  const dataSourceOptions = useMemo(() => Object.keys(dataComponents[dataFunction] ?? {}).sort(), [dataComponents, dataFunction]);
  const technical = components.Technical ?? {};
  const signalComponents = components.Signal ?? {};
  const orderComponents = components.Order ?? {};
  const simulationComponents = components.Simulation ?? {};
  const validationComponents = components.Validation ?? {};
  const bestTrialComponents = components["Best Trial"] ?? {};
  const optimizerComponents = components.Optimization ?? {};
  const indicatorSchema = technical[indicatorFunction]?.[indicatorSource];
  const signalSchema = signalComponents[signalFunction]?.[signalSource];
  const orderSchema = orderComponents[orderFunction]?.[orderSource];
  const simulationSchema = simulationComponents[simulationFunction]?.[simulationSource];
  const simulationFunctionOptions = useMemo(() => Object.keys(simulationComponents).sort(), [simulationComponents]);
  const simulationSourceOptions = useMemo(
    () => Object.keys(simulationComponents[simulationFunction] ?? {}).sort(),
    [simulationComponents, simulationFunction],
  );
  const activeStrategyComponents = components[strategyComponentCategory] ?? {};
  const validationSchema = validationComponents[validationFunction]?.[validationSource];
  const bestTrialSchema = bestTrialComponents[bestTrialFunction]?.[bestTrialSource];
  const hasSavedStrategy = Boolean(
    workspaceModel?.active?.execution_template_id ||
    workspaceModel?.templates?.some((template) => template.runner === selectedRunner) ||
    workspaceModel?.active?.strategy_id ||
    workspaceModel?.strategies.length,
  );
  const transformSpecs = workspaceModel?.transforms.flatMap((set) => set.transforms) ?? [];
  const executorOptions = useMemo(() => Object.values(executors).sort((a, b) => (a.label ?? a.runner).localeCompare(b.label ?? b.runner)), [executors]);
  const evaluatorOptions = useMemo(() => Object.values(evaluators).sort((a, b) => (a.label ?? a.evaluator).localeCompare(b.label ?? b.evaluator)), [evaluators]);
  const selectedExecutor = executors[selectedRunner];
  const activeEvaluator = evaluators[selectedEvaluator];
  const activeEvaluatorSchema = activeEvaluator?.config_schema;
  const selectedExecutorSchema = selectedExecutor?.config_schema;
  const executorSections = useMemo(() => selectedExecutor?.config_builder?.sections ?? [], [selectedExecutor]);
  const instructionSections = useMemo(
    () => executorSections.filter((section) => section.multiple && section.component_category),
    [executorSections],
  );
  const hasInstructionCategory = (category: string) =>
    instructionSections.some((section) => section.key === category || section.component_category === category);
  const activeTemplateSection =
    executorSections.find((section) => section.key === strategyComponentCategory) ??
    instructionSections.find((section) => section.component_category === strategyComponentCategory) ??
    executorSections[0];
  const activeTemplateCategory = activeTemplateSection?.component_category ?? "";
  const activeTemplateComponents = components[activeTemplateCategory] ?? {};
  const activeTemplateState = activeTemplateSection ? templateSections[activeTemplateSection.key] : undefined;
  const activeTemplateFunction = activeTemplateState?.function ?? activeTemplateSection?.default_function ?? Object.keys(activeTemplateComponents).sort()[0] ?? "";
  const activeTemplateSource =
    activeTemplateState?.source ??
    activeTemplateSection?.default_source ??
    Object.keys(activeTemplateComponents[activeTemplateFunction] ?? {}).sort()[0] ??
    "Internal";
  const activeTemplateSchema = activeTemplateComponents[activeTemplateFunction]?.[activeTemplateSource];
  const isTradingRunner = selectedRunner === "trading.backtest";
  const editableChart = charts.find((chart) => chart.id === editingChartId) ?? charts[0] ?? null;
  const editableResolvedRecord = store?.records.find((record) => record.id === (editableChart ? resolveChartDatasetId(editableChart) : null)) ?? null;
  const editableRecord = (editableChart?.datasetRole ?? "fixed") === "fixed"
    ? editableResolvedRecord ?? selected ?? rawRecord
    : editableResolvedRecord;
  const editableColumns = editableRecord?.columns ?? [];
  const editableNumericColumns = numericColumns(editableRecord);

  async function refresh(id = workspaceId) {
    if (!id) return;
    const summary = await api<StoreSummary>(`/workspaces/${id}/store`);
    setStore(summary);
    if (!selectedId && summary.records.length) setSelectedId(summary.records[0].id);
  }

  async function loadFrame(recordId: string, setter = setFrame) {
    if (!workspaceId) return;
    const nextFrame = await api<FrameResponse>(`/workspaces/${workspaceId}/records/${recordId}/frame?limit=1500`);
    setter(nextFrame);
  }

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function applyCollectionResult(result: CollectionResponse) {
    setStore(result.store);
    setPrepareSourceId(result.collection.id);
    setSelectedCollectionId(result.collection.id);
    setWorkingCollectionId(result.collection.id);
    const firstDatasetId = result.dataset_ids[0] ?? result.collection.dataframe_id ?? null;
    if (firstDatasetId) {
      setSelectedId(firstDatasetId);
      setTransformDatasetId(firstDatasetId);
      setBacktestDatasetId(firstDatasetId);
      setOptimizeDatasetId(firstDatasetId);
    }
  }

  async function createNoiseCollection() {
    if (!workspaceId || !prepareSourceId) return;
    const result = await api<CollectionResponse>(`/workspaces/${workspaceId}/collections/mutate/gaussian-noise`, {
      method: "POST",
      body: JSON.stringify({
        source_id: prepareSourceId,
        n_trajectories: noiseCount,
        stddev: noiseStddev,
      }),
    });
    applyCollectionResult(result);
  }

  async function splitPrepareSource() {
    if (!workspaceId || !prepareSourceId) return;
    const result = await api<CollectionResponse>(`/workspaces/${workspaceId}/collections/split`, {
      method: "POST",
      body: JSON.stringify({
        source_id: prepareSourceId,
        method: splitMethod,
        train_ratio: splitTrainRatio,
        val_ratio: splitValRatio,
        test_ratio: splitTestRatio,
        n_folds: splitFolds,
      }),
    });
    applyCollectionResult(result);
  }

  async function prepareCollectionWithCalculator() {
    if (!workspaceId || !prepareSourceId || !prepareRecipeId) return;
    const result = await api<CollectionResponse>(`/workspaces/${workspaceId}/collections/prepare/calculator`, {
      method: "POST",
      body: JSON.stringify({
        source_id: prepareSourceId,
        recipe_record_id: prepareRecipeId,
      }),
    });
    applyCollectionResult(result);
  }

  useEffect(() => {
    runAction(async () => {
      const [workspace, loadedComponents, loadedExecutors, loadedEvaluators] = await Promise.all([
        api<{ id: string }>("/workspaces", {
          method: "POST",
          body: JSON.stringify({ name: "MVP" }),
        }),
        api<Components>("/components"),
        api<Executors>("/executors"),
        api<Evaluators>("/evaluators"),
      ]);
      setComponents(loadedComponents);
      setExecutors(loadedExecutors);
      setEvaluators(loadedEvaluators);
      setWorkspaceId(workspace.id);
      const summary = await api<StoreSummary>(`/workspaces/${workspace.id}/store`);
      setStore(summary);
    });
  }, []);

  useEffect(() => {
    if (!indicatorSchema) return;
    const properties = indicatorSchema.properties ?? {};
    const defaults = defaultsFor(indicatorSchema);
    const outputNames = defaults.output_names;
    setIndicatorParams(defaults);
    setIndicatorName(String(properties.name?.default ?? indicatorFunction));
    if (outputNames && typeof outputNames === "object") {
      const first = Object.values(outputNames)[0];
      if (typeof first === "string") setIndicatorName(first);
    }
  }, [indicatorFunction, indicatorSource]);

  useEffect(() => {
    if (dataSchema) setDataParams(defaultsFor(dataSchema));
  }, [dataCategory, dataFunction, dataSource]);

  useEffect(() => {
    if (!dataFunctionOptions.length || dataFunctionOptions.includes(dataFunction)) return;
    setDataFunction(dataFunctionOptions[0]);
  }, [dataFunction, dataFunctionOptions]);

  useEffect(() => {
    if (!dataSourceOptions.length || dataSourceOptions.includes(dataSource)) return;
    setDataSource(dataSourceOptions[0]);
  }, [dataSource, dataSourceOptions]);

  useEffect(() => {
    if (prepareSourceOptions.length && !prepareSourceOptions.some((option) => option.id === prepareSourceId)) {
      setPrepareSourceId(prepareSourceOptions[0].id);
    }
  }, [prepareSourceOptions, prepareSourceId]);

  useEffect(() => {
    if (collectionArtifacts.length && !collectionArtifacts.some((collection) => collection.id === workingCollectionId)) {
      setWorkingCollectionId(collectionArtifacts.at(-1)?.id ?? "");
    }
  }, [collectionArtifacts, workingCollectionId]);

  useEffect(() => {
    if (calculatorRecipeRecords.length && !calculatorRecipeRecords.some((record) => record.id === prepareRecipeId)) {
      setPrepareRecipeId(calculatorRecipeRecords[0].id);
    }
  }, [calculatorRecipeRecords, prepareRecipeId]);

  useEffect(() => {
    if (signalSchema) setSignalParams(defaultsFor(signalSchema));
  }, [signalFunction, signalSource]);

  useEffect(() => {
    if (orderSchema) setOrderParams(defaultsFor(orderSchema));
  }, [orderFunction, orderSource]);

  useEffect(() => {
    if (simulationSchema) setSimulationParams(defaultsFor(simulationSchema));
  }, [simulationSchema]);

  useEffect(() => {
    if (selectedExecutorSchema) setExecutorConfig(defaultsFor(selectedExecutorSchema));
  }, [selectedExecutorSchema]);

  useEffect(() => {
    if (activeEvaluatorSchema) setEvaluatorConfig(defaultsFor(activeEvaluatorSchema));
  }, [activeEvaluatorSchema]);

  function defaultTemplateSectionState(section: ExecutorSection, current?: TemplateSectionState): TemplateSectionState {
    const categoryComponents = section.component_category ? components[section.component_category] ?? {} : {};
    const functions = Object.keys(categoryComponents).sort();
    const fn = current?.function && categoryComponents[current.function]
      ? current.function
      : section.default_function && categoryComponents[section.default_function]
        ? section.default_function
        : functions[0] ?? "";
    const sources = Object.keys(categoryComponents[fn] ?? {}).sort();
    const source = current?.source && categoryComponents[fn]?.[current.source]
      ? current.source
      : section.default_source && categoryComponents[fn]?.[section.default_source]
        ? section.default_source
        : sources[0] ?? "Internal";
    const schema = categoryComponents[fn]?.[source];
    return {
      function: fn,
      source,
      params: current?.params && current.function === fn && current.source === source ? current.params : defaultsFor(schema),
      items: current?.items ?? [],
    };
  }

  useEffect(() => {
    setTemplateSections((current) => {
      const next: Record<string, TemplateSectionState> = {};
      for (const section of executorSections) {
        if (!section.component_category) continue;
        next[section.key] = defaultTemplateSectionState(section, current[section.key]);
      }
      return next;
    });
  }, [executorSections, components]);

  useEffect(() => {
    if (simulationFunctionOptions.length && !simulationFunctionOptions.includes(simulationFunction)) {
      setSimulationFunction(simulationFunctionOptions[0]);
    }
  }, [simulationFunctionOptions, simulationFunction]);

  useEffect(() => {
    if (simulationSourceOptions.length && !simulationSourceOptions.includes(simulationSource)) {
      setSimulationSource(simulationSourceOptions[0]);
    }
  }, [simulationSourceOptions, simulationSource]);

  function firstColumnChoice(key: string, options: string[], current?: unknown): string | null {
    if (!options.length) return null;
    if (key === "value1" && backtestSignalColumns[0]) return backtestSignalColumns[0];
    if (key === "value2" && backtestSignalColumns[1]) return backtestSignalColumns[1];
    if (typeof current === "string" && options.includes(current)) return current;
    if (["on_price", "close_on_completion", "real", "close"].includes(key) && options.includes("close")) return "close";
    if (key === "open" && options.includes("open")) return "open";
    if (key === "high" && options.includes("high")) return "high";
    if (key === "low" && options.includes("low")) return "low";
    return options[0];
  }

  function syncColumnParams(
    schema: { properties?: Record<string, JsonSchema> } | undefined,
    values: Record<string, unknown>,
    setValues: React.Dispatch<React.SetStateAction<Record<string, unknown>>>,
    options: string[],
  ) {
    if (!schema || !options.length) return;
    const updates: Record<string, string> = {};
    for (const [key, field] of Object.entries(schema.properties ?? {})) {
      const columnField = field.use_variable_options || ["column", "real", "open", "high", "low", "close", "value1", "value2", "on_price", "close_on_completion"].includes(key);
      if (!columnField) continue;
      const next = firstColumnChoice(key, options, values[key]);
      if (next && values[key] !== next) updates[key] = next;
    }
    if (Object.keys(updates).length) setValues((current) => ({ ...current, ...updates }));
  }

  useEffect(() => {
    syncColumnParams(signalSchema, signalParams, setSignalParams, backtestColumnOptions);
  }, [signalSchema, signalParams, backtestColumnOptions]);

  useEffect(() => {
    syncColumnParams(orderSchema, orderParams, setOrderParams, backtestColumnOptions);
  }, [orderSchema, orderParams, backtestColumnOptions]);

  useEffect(() => {
    syncColumnParams(simulationSchema, simulationParams, setSimulationParams, backtestColumnOptions);
  }, [simulationSchema, simulationParams, backtestColumnOptions]);

  useEffect(() => {
    syncColumnParams(selectedExecutorSchema, executorConfig, setExecutorConfig, backtestColumnOptions);
  }, [selectedExecutorSchema, executorConfig, backtestColumnOptions]);

  useEffect(() => {
    if (!activeTemplateSection || !activeTemplateState) return;
    if (!activeTemplateSection.column_options) return;
    if (!activeTemplateSchema || !backtestColumnOptions.length) return;
    const updates: Record<string, string> = {};
    for (const [key, field] of Object.entries(activeTemplateSchema.properties ?? {})) {
      const columnField = field.use_variable_options || ["column", "real", "open", "high", "low", "close", "value1", "value2", "on_price", "close_on_completion"].includes(key);
      if (!columnField) continue;
      const next = firstColumnChoice(key, backtestColumnOptions, activeTemplateState.params[key]);
      if (next && activeTemplateState.params[key] !== next) updates[key] = next;
    }
    if (Object.keys(updates).length) {
      setTemplateSections((current) => ({
        ...current,
        [activeTemplateSection.key]: {
          ...current[activeTemplateSection.key],
          params: { ...current[activeTemplateSection.key]?.params, ...updates },
        },
      }));
    }
  }, [activeTemplateSection, activeTemplateState, activeTemplateSchema, backtestColumnOptions]);

  useEffect(() => {
    if (validationSchema) setValidationParams(defaultsFor(validationSchema));
  }, [validationFunction, validationSource]);

  useEffect(() => {
    if (bestTrialSchema) setBestTrialParams(defaultsFor(bestTrialSchema));
  }, [bestTrialFunction, bestTrialSource]);

  useEffect(() => {
    if (!rawRecord) return;
    if (!transformDatasetId || !store?.records.some((record) => record.id === transformDatasetId)) {
      setTransformDatasetId(rawRecord.id);
    }
  }, [rawRecord?.id, store?.records, transformDatasetId]);

  useEffect(() => {
    const fallback = indicatorRecord ?? rawRecord;
    if (!fallback) return;
    if (!backtestDatasetId || !store?.records.some((record) => record.id === backtestDatasetId)) {
      setBacktestDatasetId(fallback.id);
    }
  }, [indicatorRecord?.id, rawRecord?.id, store?.records, backtestDatasetId]);

  useEffect(() => {
    const fallback = indicatorRecord ?? rawRecord;
    if (!fallback) return;
    if (!optimizeDatasetId || !store?.records.some((record) => record.id === optimizeDatasetId)) {
      setOptimizeDatasetId(fallback.id);
    }
  }, [indicatorRecord?.id, rawRecord?.id, store?.records, optimizeDatasetId]);

  useEffect(() => {
    const recipeNames = optimizeRecipeTransforms.map((transform) => transform.name).filter(Boolean) as string[];
    if (!recipeNames.length) return;
    setOptParams((current) => {
      const next = current.filter((parameter) => parameter.target !== "Transform" || recipeNames.includes(String(parameter.name)));
      return next.length === current.length ? current : next;
    });
    setNewOptParam((current) =>
      current.target === "Transform" && (!current.name || !recipeNames.includes(String(current.name)))
        ? { ...current, name: recipeNames[0] }
        : current,
    );
  }, [optimizeRecipeTransforms]);

  useEffect(() => {
    localStorage.setItem("quantapy.activeLayout", JSON.stringify({ id: "active", name: layoutName, charts }));
  }, [charts, layoutName]);

  useEffect(() => {
    localStorage.setItem("quantapy.savedLayouts", JSON.stringify(savedLayouts));
  }, [savedLayouts]);

  useEffect(() => {
    if (!selectedId || charts.some((chart) => chart.datasetId)) return;
    setCharts((current) => current.map((chart) => ({ ...chart, datasetId: selectedId })));
  }, [selectedId, charts]);

  useEffect(() => {
    if (!workspaceId || !selectedId) return;
    loadFrame(selectedId).catch((err) => setError(err.message));
  }, [workspaceId, selectedId, selectedRecordSignature]);

  useEffect(() => {
    if (!latestBacktest || !workspaceId) return;
    loadFrame(latestBacktest.id, setSignalFrame).catch((err) => setError(err.message));
  }, [latestBacktest?.id, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !providerKey) return;
    api(`/workspaces/${workspaceId}/provider-keys`, {
      method: "PUT",
      body: JSON.stringify({ provider: "FMP", api_key: providerKey }),
    }).catch((err) => setError(err.message));
  }, [workspaceId]);

  useEffect(() => {
    if (!store?.latest_run_id) return;
    if (!activeRunId || !studyRuns.some((run) => run.run_id === activeRunId)) {
      setActiveRunId(store.latest_run_id);
    }
  }, [store?.latest_run_id, studyRuns, activeRunId]);

  useEffect(() => {
    if (activeFold === "all") return;
    if (activeRun) {
      if (!activeRun.folds.includes(Number.parseInt(activeFold, 10))) setActiveFold("all");
      return;
    }
    if (collectionFoldOptions.length && !collectionFoldOptions.includes(activeFold)) setActiveFold("all");
  }, [activeRun?.run_id, activeRun?.folds, activeRun, activeFold, collectionFoldOptions]);

  useEffect(() => {
    if (collectionSplitOptions.length && !collectionSplitOptions.includes(activeSplit)) {
      setActiveSplit(collectionSplitOptions.includes("test") ? "test" : collectionSplitOptions[0]);
    }
  }, [collectionSplitOptions, activeSplit]);

  useEffect(() => {
    if (executorOptions.length && !executors[selectedRunner]) {
      setSelectedRunner(executorOptions[0].runner);
    }
  }, [executorOptions, executors, selectedRunner]);

  useEffect(() => {
    if (evaluatorOptions.length && !evaluators[selectedEvaluator]) {
      setSelectedEvaluator(evaluatorOptions[0].evaluator);
    }
  }, [evaluatorOptions, evaluators, selectedEvaluator]);

  useEffect(() => {
    if (!hasInstructionCategory(strategyComponentCategory)) {
      setStrategyComponentCategory(executorSections[0]?.key ?? "");
    }
  }, [strategyComponentCategory, instructionSections, executorSections]);

  function setParam(key: string, value: unknown) {
    setIndicatorParams((current) => ({ ...current, [key]: value }));
  }

  function setIndicatorInputParam(key: string, value: unknown) {
    setIndicatorParams((current) => ({ ...current, [key]: value }));
  }

  function coerceParam(schema: JsonSchema, value: string): unknown {
    if (schema.type === "array") {
      return value.split(",").map((item) => item.trim()).filter(Boolean);
    }
    if (schema.type === "integer") return Number.parseInt(value, 10);
    if (schema.type === "number") return Number.parseFloat(value);
    return value;
  }

  function latestBacktestParentId(summary: StoreSummary): string | null {
    const backtest = [...summary.records].reverse().find((record) => record.kind === "backtest");
    return backtest?.parents[0]?.id ?? null;
  }

  function latestRecordByArtifact(artifact: string, records = store?.records ?? []): StoreRecord | null {
    return [...records].reverse().find((record) => artifactOf(record) === artifact) ?? null;
  }

  function contextRecordByRole(role: ChartDatasetRole | undefined): StoreRecord | null {
    const resolvedRole = role ?? "fixed";
    if (resolvedRole === "fixed") return null;

    if (!activeRunId) {
      if (resolvedRole === "source") return indicatorRecord ?? selected ?? rawRecord;
      if (resolvedRole === "signals" || resolvedRole === "events") return latestBacktest ?? null;
      if (resolvedRole === "portfolio_outputs") return latestRecordByArtifact("portfolio_outputs");
      if (resolvedRole === "portfolio_metrics") return latestRecordByArtifact("portfolio_metrics") ?? latestRecordByArtifact("operation_metrics");
      if (resolvedRole === "trials") return latestRecordByArtifact("optimization_trials");
      if (resolvedRole === "fold_summary") {
        return latestRecordByArtifact("validation_summary") ?? latestRecordByArtifact("optimization_summary");
      }
      return null;
    }

    const foldValue = activeFold === "all" ? null : Number.parseInt(activeFold, 10);
    const splitMatches = (record: StoreRecord) => !record.split || record.split === activeSplit;
    const foldMatches = (record: StoreRecord) => foldValue === null || record.fold === foldValue;
    const candidates = [...(activeRun?.artifacts?.length ? activeRun.artifacts : activeRunRecords)].reverse();

    if (resolvedRole === "fold_summary") {
      return (
        candidates.find((record) => ["validation_summary", "optimization_summary"].includes(String(artifactOf(record)))) ??
        null
      );
    }

    if (resolvedRole === "source") {
      const matching = (record: StoreRecord) =>
        foldMatches(record) && (activeFold === "all" || splitMatches(record));
      return (
        candidates.find((record) => artifactOf(record) === "indicators" && matching(record)) ??
        candidates.find((record) => artifactOf(record) === "prepared_data" && matching(record)) ??
        candidates.find((record) => artifactOf(record) === "calculator" && matching(record)) ??
        candidates.find((record) => artifactOf(record) === "source" && matching(record)) ??
        (activeFold === "all"
          ? candidates.find((record) => artifactOf(record) === "indicators") ??
            candidates.find((record) => artifactOf(record) === "prepared_data") ??
            candidates.find((record) => artifactOf(record) === "calculator") ??
            candidates.find((record) => artifactOf(record) === "source") ??
            null
          : null)
      );
    }

    const artifactForRole =
      resolvedRole === "signals" || resolvedRole === "events"
        ? "backtest"
          : resolvedRole === "trials"
            ? "optimization_trials"
            : resolvedRole === "portfolio_metrics"
              ? "portfolio_metrics"
              : resolvedRole;

    if (foldValue !== null) {
      return (
        candidates.find(
          (record) =>
            artifactOf(record) === artifactForRole &&
            foldMatches(record) &&
            (resolvedRole === "trials" || splitMatches(record)),
        ) ?? null
      );
    }

    return (
      candidates.find((record) => artifactOf(record) === artifactForRole && (resolvedRole === "trials" || splitMatches(record))) ??
      (resolvedRole === "portfolio_metrics"
        ? candidates.find((record) => artifactOf(record) === "operation_metrics")
        : null) ??
      candidates.find((record) => artifactOf(record) === artifactForRole) ??
      null
    );
  }

  function resolveChartDatasetId(chart: ChartConfig): string | null {
    if (chart.collectionId) {
      const collection = collectionArtifacts.find((artifact) => artifact.id === chart.collectionId) ?? null;
      const allLeaves = collectionLeafRecords(collection);
      const leaves = filterCollectionLeaves(allLeaves, activeFold, activeSplit);
      const visibleLeaves = leaves.length ? leaves : allLeaves;
      return visibleLeaves[Math.min(Math.max(chart.collectionIndex ?? 0, 0), Math.max(visibleLeaves.length - 1, 0))]?.record.id ?? null;
    }
    return (chart.datasetRole ?? "fixed") === "fixed"
      ? chart.datasetId ?? null
      : contextRecordByRole(chart.datasetRole)?.id ?? null;
  }

  function resolveSignalDatasetId(chart: ChartConfig): string | null {
    return (chart.signalDatasetRole ?? "fixed") === "fixed"
      ? chart.signalDatasetId ?? null
      : contextRecordByRole(chart.signalDatasetRole)?.id ?? null;
  }

  function latestRawId(summary: StoreSummary): string | null {
    return [...summary.records].reverse().find((record) => record.kind === "raw")?.id ?? null;
  }

  function latestCollection(summary: StoreSummary, role?: string): ArtifactRecord | null {
    return [...(summary.artifacts ?? [])]
      .reverse()
      .find((artifact) => artifact.artifact_type === "collection" && (!role || artifact.role === role)) ?? null;
  }

  function coverageWarning(record: StoreRecord | null): string | null {
    const warning = record?.attrs.coverage_warning;
    return typeof warning === "string" && warning ? warning : null;
  }

  function latestFetchWarning(summary: StoreSummary): string | null {
    const latestRaw = [...summary.records].reverse().find((record) => record.kind === "raw") ?? null;
    return coverageWarning(latestRaw);
  }

  async function deleteSelectedRecord() {
    if (!workspaceId || !selected) return;
    const summary = await api<StoreSummary>(`/workspaces/${workspaceId}/records/${selected.id}?cascade=true`, {
      method: "DELETE",
    });
    setStore(summary);
    setSignalFrame(null);
    const nextSelectedId = summary.visible_records[0]?.id ?? summary.records[0]?.id ?? null;
    setSelectedId(nextSelectedId);
    if (nextSelectedId) {
      await loadFrame(nextSelectedId);
    } else {
      setFrame(null);
    }
  }

  async function saveProviderKey() {
    if (!workspaceId || !providerKey) return;
    localStorage.setItem("quantapy.fmpKey", providerKey);
    await api(`/workspaces/${workspaceId}/provider-keys`, {
      method: "PUT",
      body: JSON.stringify({ provider: "FMP", api_key: providerKey }),
    });
    setSettingsOpen(false);
  }

  async function uploadCsvFile(file: File): Promise<string> {
    if (!workspaceId) throw new Error("Workspace is not ready");
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/workspaces/${workspaceId}/uploads`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail ?? `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    return payload.path;
  }

  function renderNode(node: StoreNode, depth = 0): React.ReactNode {
    return (
      <div className="tree-node" key={node.id}>
        <button
          className={node.id === selectedId ? "record active" : "record"}
          style={{ paddingLeft: 10 + depth * 14 }}
          onClick={() => setSelectedId(node.id)}
        >
          <span>{node.label || node.name}</span>
          <small>
            {node.kind} · {node.shape[0]} x {node.shape[1]}
          </small>
        </button>
        {node.children.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  }

  function setOutputParam(outputKey: string, value: string) {
    setIndicatorParams((current) => ({
      ...current,
      output_names: { ...((current.output_names as Record<string, string>) ?? {}), [outputKey]: value },
    }));
  }

  function renderSchemaFields(
    schema: { properties?: Record<string, JsonSchema> } | undefined,
    values: Record<string, unknown>,
    onChange: (key: string, value: unknown) => void,
    skip: string[] = ["name", "output_names", "display"],
    columnOptions: string[] = [],
  ) {
    return Object.entries(schema?.properties ?? {})
      .filter(([key]) => !skip.includes(key))
      .filter(([, field]) =>
        Object.entries(field.show_if ?? {}).every(([dependency, expected]) => values[dependency] === expected),
      )
      .slice(0, 10)
      .map(([key, field]) => (
        <label className="field" key={key}>
          <span>{key}</span>
          {field.widget_type === "file" ? (
            <>
              <input
                type="file"
                accept=".csv,.tsv,.dat,.json,.txt,.log,.out,.err,text/*,application/json"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  uploadCsvFile(file)
                    .then((path) => onChange(key, path))
                    .catch((err) => setError(err instanceof Error ? err.message : String(err)));
                }}
              />
              {values[key] ? <small>{String(values[key])}</small> : null}
            </>
          ) : (field.use_variable_options || ["real", "open", "high", "low", "close", "value1", "value2", "on_price", "close_on_completion"].includes(key)) && columnOptions.length ? (
            <select value={String(values[key] ?? field.default ?? columnOptions[0])} onChange={(event) => onChange(key, event.target.value)}>
              {columnOptions.map((column) => (
                <option key={column}>{column}</option>
              ))}
            </select>
          ) : field.enum ? (
            <select value={String(values[key] ?? "")} onChange={(event) => onChange(key, coerceParam(field, event.target.value))}>
              {field.enum.map((option) => (
                <option key={String(option)} value={String(option)}>
                  {String(option)}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={displayValue(values[key])}
              type={
                field.widget_type === "date"
                  ? "date"
                  : field.type === "integer" || field.type === "number"
                    ? "number"
                    : "text"
              }
              onChange={(event) => onChange(key, coerceParam(field, event.target.value))}
            />
          )}
        </label>
      ));
  }

  function updateTemplateSection(key: string, patch: Partial<TemplateSectionState>) {
    const section = executorSections.find((item) => item.key === key);
    setTemplateSections((current) => {
      const existing = current[key] ?? (section ? defaultTemplateSectionState(section) : { function: "", source: "Internal", params: {}, items: [] });
      return { ...current, [key]: { ...existing, ...patch } };
    });
  }

  function updateTemplateSectionParam(sectionKey: string, paramKey: string, value: unknown) {
    setTemplateSections((current) => {
      const section = executorSections.find((item) => item.key === sectionKey);
      const existing = current[sectionKey] ?? (section ? defaultTemplateSectionState(section) : { function: "", source: "Internal", params: {}, items: [] });
      return {
        ...current,
        [sectionKey]: {
          ...existing,
          params: { ...existing.params, [paramKey]: value },
        },
      };
    });
  }

  function currentTemplateComponent(section: ExecutorSection): ComponentSpec | null {
    const state = templateSections[section.key];
    if (!state?.function) return null;
    return {
      category: section.component_category ?? "",
      function: state.function,
      source: state.source || "Internal",
      name: null,
      params: { ...state.params },
    };
  }

  function addTemplateSectionItem(section: ExecutorSection) {
    const component = currentTemplateComponent(section);
    if (!component) return;
    setTemplateSections((current) => {
      const existing = current[section.key] ?? defaultTemplateSectionState(section);
      return {
        ...current,
        [section.key]: { ...existing, items: [...existing.items, component] },
      };
    });
  }

  function removeTemplateSectionItem(sectionKey: string, index: number) {
    setTemplateSections((current) => {
      const existing = current[sectionKey];
      if (!existing) return current;
      return {
        ...current,
        [sectionKey]: { ...existing, items: existing.items.filter((_, itemIndex) => itemIndex !== index) },
      };
    });
  }

  function buildExecutionTemplateSections(): Record<string, unknown> {
    const sections: Record<string, unknown> = {};
    for (const section of executorSections) {
      if (!section.component_category) continue;
      const state = templateSections[section.key];
      if (!state) continue;
      sections[section.key] = section.multiple
        ? state.items
        : currentTemplateComponent(section);
    }
    return sections;
  }

  function setNewOptField(key: keyof typeof newOptParam, value: string | number) {
    setNewOptParam((current) => ({ ...current, [key]: value }));
  }

  function optSubjectOptions() {
    if (newOptParam.target === "Transform") {
      const recipeOptions = optimizeRecipeTransforms.map((spec) => spec.name).filter(Boolean) as string[];
      if (recipeOptions.length) return recipeOptions;
      return transformSpecs.map((spec) => spec.name || spec.function).filter(Boolean) as string[];
    }
    if (newOptParam.target === "Signal") {
      return strategySignals.map((signal, index) => `${index}: ${signal.function}`);
    }
    if (newOptParam.target === "Order") {
      return strategyOrders.map((order, index) => `${index}: ${order.function}`);
    }
    if (newOptParam.target === "Simulation") {
      return ["0: Selected runner"];
    }
    return [];
  }

  function addOptimizationParameter() {
    const subjectIndex = newOptParam.index === "" ? null : Number.parseInt(String(newOptParam.index), 10);
    const parameter = {
      ...newOptParam,
      name: newOptParam.target === "Transform" ? newOptParam.name : "",
      index: newOptParam.target === "Transform" ? "" : String(subjectIndex ?? 0),
      low: Number(newOptParam.low),
      high: Number(newOptParam.high),
    };
    if (!parameter.param || Number.isNaN(parameter.low) || Number.isNaN(parameter.high)) return;
    if (parameter.target === "Transform" && !parameter.name) return;
    setOptParams((current) => [...current, parameter]);
  }

  function updateChart(id: string, patch: Partial<ChartConfig>) {
    setCharts((current) => current.map((chart) => (chart.id === id ? { ...chart, ...patch } : chart)));
  }

  function updateChartMappings(id: string, mappings: Partial<ChartConfig["mappings"]>) {
    setCharts((current) =>
      current.map((chart) =>
        chart.id === id ? { ...chart, mappings: { ...chart.mappings, ...mappings } } : chart,
      ),
    );
  }

  function setChartColumns(chart: ChartConfig, columns: string[]) {
    updateChartMappings(chart.id, { y: columns });
  }

  function addChart(type: ChartType = "timeseries", datasetOverride?: string | null) {
    const datasetId = datasetOverride ?? selectedId ?? rawRecord?.id ?? null;
    const addKey = `${type}:${datasetId ?? "none"}`;
    const now = Date.now();
    if (lastChartAdd.current?.key === addKey && now - lastChartAdd.current.at < 400) return;
    lastChartAdd.current = { key: addKey, at: now };
    const record = store?.records.find((item) => item.id === datasetId) ?? rawRecord;
    const numeric = numericColumns(record);
    const chart: ChartConfig = {
      id: makeChartId(),
      type,
      title:
        type === "ohlc"
          ? "OHLC"
          : type === "table"
            ? "Table"
            : type === "scatter3d"
              ? "3D Scatter"
              : type === "scatter2d"
                ? "2D Scatter"
                : type === "metrics"
                  ? "Metrics"
                : type === "text"
                  ? "Text"
                : type === "calculator"
                  ? "Calculator"
                  : "Time Series",
      datasetId,
      artifactId: type === "text" ? store?.artifacts?.find((artifact) => ["text", "raw_file"].includes(artifact.role))?.id ?? null : null,
      width: type === "ohlc" ? "full" : "normal",
      height: "normal",
      widthUnits: type === "ohlc" ? 12 : type === "calculator" ? 5 : type === "text" ? 6 : 6,
      heightPx: type === "ohlc" ? 390 : type === "calculator" ? 420 : type === "text" ? 360 : 310,
      mappings: {
        x: type === "scatter2d" || type === "scatter3d" ? numeric[0] ?? "close" : "date",
        y: type === "table" || type === "metrics" ? record?.columns.slice(0, type === "metrics" ? 18 : 8) ?? [] : [numeric[1] ?? numeric[0] ?? "close"],
        z: numeric[2] ?? numeric[0] ?? "close",
        open: "open",
        high: "high",
        low: "low",
        close: "close",
      },
    };
    setCharts((current) => [...current, chart]);
    setEditingChartId(type === "calculator" ? null : chart.id);
  }

  function defaultViewForRecord(record: StoreRecord): ChartType {
    if (record.attrs.artifact === "portfolio_metrics" || record.kind === "metrics" && record.shape[0] <= 2) return "metrics";
    if (canChart(record)) return "ohlc";
    if (record.columns.includes("portfolio_value")) return "timeseries";
    if (record.columns.filter((column) => numericColumns(record).includes(column)).length >= 3) return "scatter3d";
    return "table";
  }

  function addRecordToCanvas(record: StoreRecord, type: ChartType = defaultViewForRecord(record)) {
    setSelectedId(record.id);
    addChart(type, record.id);
  }

  function addArtifactToCanvas(artifact: ArtifactRecord) {
    const chart: ChartConfig = {
      ...defaultChartConfig(null),
      id: makeChartId(),
      type: "text",
      title: artifact.name,
      artifactId: artifact.id,
      datasetId: null,
      width: "wide",
      widthUnits: 8,
      heightPx: 360,
    };
    setCharts((current) => [...current, chart]);
  }

  function collectionLeafRecords(collection: ArtifactRecord | null | undefined): CollectionLeaf[] {
    return collectionLeafRecordsFromStore(store, collection);
  }

  function addCollectionPreview(collection: ArtifactRecord) {
    const leaves = collectionLeafRecords(collection);
    const first = leaves[0]?.record;
    if (!first || !store) return;
    setSelectedCollectionId(collection.id);
    showDatasetView(store, first.id);
  }

  function addCollectionToCanvas(collection: ArtifactRecord, mode: "selected" | "all" = "selected") {
    const allLeaves = collectionLeafRecords(collection);
    const contextLeaves = filterCollectionLeaves(allLeaves, activeFold, activeSplit);
    const leaves = contextLeaves.length ? contextLeaves : allLeaves;
    const first = leaves[0]?.record ?? null;
    const numeric = numericColumns(first);
    const type: ChartType = first && canChart(first) ? "ohlc" : "timeseries";
    const chart: ChartConfig = {
      id: makeChartId(),
      type,
      title: collection.name,
      datasetId: first?.id ?? null,
      collectionId: collection.id,
      collectionMode: mode,
      collectionIndex: 0,
      datasetRole: "fixed",
      width: type === "ohlc" ? "full" : "normal",
      height: "normal",
      widthUnits: type === "ohlc" ? 12 : 6,
      heightPx: type === "ohlc" ? 390 : 310,
      maxRows: 100000,
      mappings: {
        x: "date",
        y: [numeric.includes("close") ? "close" : numeric[0] ?? ""].filter(Boolean),
        z: numeric[2] ?? numeric[0] ?? "",
        open: "open",
        high: "high",
        low: "low",
        close: "close",
      },
    };
    setSelectedCollectionId(collection.id);
    setSelectedId(first?.id ?? null);
    setCharts((current) => [...current, chart]);
    setEditingChartId(chart.id);
  }

  function overlayRecordOnOhlc(record: StoreRecord) {
    const parentId = record.parents[0]?.id ?? selectedId ?? rawRecord?.id ?? null;
    setCharts((current) => {
      const targetIndex = current.findIndex((chart) => chart.type === "ohlc" && (!parentId || chart.datasetId === parentId));
      if (targetIndex >= 0) {
        return current.map((chart, index) => index === targetIndex ? { ...chart, signalDatasetId: record.id } : chart);
      }
      if (!parentId) return current;
      return [
        ...current,
        {
          ...defaultChartConfig(parentId),
          id: makeChartId(),
          title: "Candles + Signals",
          signalDatasetId: record.id,
        },
      ];
    });
    setSelectedId(record.id);
  }

  function handleDerivedDataset(sourceId: string, record: StoreRecord, summary: StoreSummary, outputColumns: string[]) {
    setStore(summary);
    setSelectedId(record.id);
    setTransformDatasetId(record.id);
    setBacktestDatasetId(record.id);
    setOptimizeDatasetId(record.id);
    setCharts((current) =>
      current.map((chart) =>
        chart.datasetId === sourceId
          ? {
              ...chart,
              datasetId: record.id,
              mappings: {
                ...chart.mappings,
                y:
                  chart.type === "calculator"
                    ? chart.mappings.y
                    : chart.type === "table"
                    ? record.columns.slice(0, 10)
                    : [...new Set([...(chart.mappings.y ?? []), ...outputColumns])],
              },
            }
          : chart,
      ),
    );
  }

  function removeChart(id: string) {
    setCharts((current) => current.filter((chart) => chart.id !== id));
    if (editingChartId === id) setEditingChartId(null);
  }

  function configureChart(id: string) {
    const chart = charts.find((item) => item.id === id);
    if (chart?.datasetId) {
      setSelectedId(chart.datasetId);
      setTransformDatasetId(chart.datasetId);
    }
    setEditingChartId(id);
  }

  function resizeChart(id: string, size: Partial<Pick<ChartConfig, "widthUnits" | "heightPx" | "width" | "height">>) {
    setCharts((current) => current.map((chart) => (chart.id === id ? { ...chart, ...size } : chart)));
  }

  function reorderChart(targetId: string, finish = false) {
    if (!draggingChartId || draggingChartId === targetId) {
      if (finish) setDraggingChartId(null);
      return;
    }
    setCharts((current) => {
      const from = current.findIndex((chart) => chart.id === draggingChartId);
      const to = current.findIndex((chart) => chart.id === targetId);
      if (from < 0 || to < 0) return current;
      const next = [...current];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
    if (finish) setDraggingChartId(null);
  }

  function saveLayout() {
    const layout: DashboardLayout = {
      id: makeChartId(),
      name: layoutName || "Research Layout",
      charts,
    };
    setSavedLayouts((current) => [layout, ...current.filter((item) => item.name !== layout.name)].slice(0, 12));
  }

  function loadLayout(layout: DashboardLayout) {
    setLayoutName(layout.name);
    setCharts(layout.charts);
    setEditingChartId(layout.charts[0]?.id ?? null);
  }

  function recordsForRun(summary: StoreSummary, runId?: string | null): StoreRecord[] {
    if (!runId) return summary.records;
    const studyRun = summary.study_runs.find((run) => run.run_id === runId);
    if (studyRun?.artifacts?.length) return studyRun.artifacts;
    const executionRun = summary.workspace?.executions?.runs.find((run) => run.id === runId);
    if (executionRun) {
      return summary.records.filter((record) =>
        [...executionRun.input_ids, ...executionRun.output_ids].includes(record.id) ||
        record.attrs.source_run_id === runId
      );
    }
    return summary.records.filter((record) => record.run_id === runId);
  }

  function latestArtifact(summary: StoreSummary, artifact: string, runId?: string | null): StoreRecord | null {
    return [...recordsForRun(summary, runId)].reverse().find((record) => artifactOf(record) === artifact) ?? null;
  }

  function applyExecutionReview(summary: StoreSummary, runId?: string | null, fallbackDatasetId?: string | null) {
    const source =
      latestArtifact(summary, "indicators", runId) ??
      latestArtifact(summary, "prepared_data", runId) ??
      latestArtifact(summary, "calculator", runId) ??
      latestArtifact(summary, "source", runId);
    const events = latestArtifact(summary, "backtest", runId);
    const metrics = latestArtifact(summary, "portfolio_metrics", runId);
    setLayoutName("Execution Review");
    setCharts([
      {
        ...defaultChartConfig(source?.id ?? fallbackDatasetId ?? null),
        title: "Candles + Signals",
        datasetRole: "source",
        signalDatasetId: events?.id ?? null,
        signalDatasetRole: "signals",
      },
      {
        id: makeChartId(),
        type: "timeseries",
        title: "Portfolio Value",
        datasetId: null,
        datasetRole: "portfolio_outputs",
        widthUnits: 6,
        heightPx: 320,
        mappings: { x: "date", y: ["portfolio_value"] },
      },
      {
        id: makeChartId(),
        type: "metrics",
        title: "Portfolio Metrics",
        datasetId: metrics?.id ?? null,
        datasetRole: "portfolio_metrics",
        widthUnits: 6,
        heightPx: 320,
        mappings: { y: metrics?.columns ?? [] },
      },
      {
        id: makeChartId(),
        type: "table",
        title: "Execution Events",
        datasetId: events?.id ?? null,
        datasetRole: "events",
        widthUnits: 12,
        heightPx: 280,
        mappings: { y: ["date", "signal", "action", "portfolio_value", "position"] },
      },
    ]);
    setSelectedId(source?.id ?? fallbackDatasetId ?? events?.id ?? null);
  }

  function showDatasetView(summary: StoreSummary, datasetId: string | null) {
    const record = summary.records.find((item) => item.id === datasetId) ?? null;
    setActiveRunId("");
    setActiveFold("all");
    setActiveSplit("test");
    setSelectedId(datasetId);
    setLayoutName("Data View");
    setCharts([
      {
        ...defaultChartConfig(datasetId),
        title: record?.label || record?.name || "OHLC",
        datasetRole: "fixed",
      },
      {
        id: makeChartId(),
        type: "timeseries",
        title: "Volume",
        datasetId,
        datasetRole: "fixed",
        widthUnits: 6,
        heightPx: 260,
        mappings: { x: "date", y: record?.columns.includes("volume") ? ["volume"] : [] },
      },
      {
        id: makeChartId(),
        type: "table",
        title: "Rows",
        datasetId,
        datasetRole: "fixed",
        widthUnits: 6,
        heightPx: 260,
        mappings: { y: record?.columns.slice(0, 8) ?? [] },
      },
    ]);
  }

  function applyTemplate(template: "review" | "optimization" | "data") {
    const datasetId = selectedId ?? rawRecord?.id ?? null;
    const indicatorId = indicatorRecord?.id ?? datasetId;
    const backtestId = latestBacktest?.id ?? null;
    if (template === "review") {
      setLayoutName("Execution Review");
      setCharts([
        {
          ...defaultChartConfig(indicatorId),
          title: "Candles + Signals",
          datasetRole: "source",
          signalDatasetId: backtestId,
          signalDatasetRole: "signals",
        },
        {
          id: makeChartId(),
          type: "timeseries",
          title: "Portfolio Value",
          datasetId: backtestId,
          datasetRole: "portfolio_outputs",
          mappings: { x: "date", y: ["portfolio_value"] },
        },
        {
          id: makeChartId(),
          type: "metrics",
          title: "Portfolio Metrics",
          datasetId: latestPortfolioMetrics?.id ?? null,
          datasetRole: "portfolio_metrics",
          mappings: { y: latestPortfolioMetrics?.columns ?? [] },
        },
        {
          id: makeChartId(),
          type: "table",
          title: "Execution Events",
          datasetId: backtestId,
          datasetRole: "events",
          mappings: { y: ["date", "signal", "action", "portfolio_value", "position"] },
        },
      ]);
      return;
    }
    if (template === "optimization") {
      setLayoutName("Optimization Review");
      setCharts([
        {
          ...defaultChartConfig(datasetId),
          title: "Optimized Candles + Signals",
          datasetRole: "source",
          signalDatasetRole: "signals",
        },
        {
          id: makeChartId(),
          type: "timeseries",
          title: "Selected Portfolio",
          datasetId,
          datasetRole: "portfolio_outputs",
          mappings: { x: "date", y: ["portfolio_value", "drawdown"] },
        },
        {
          id: makeChartId(),
          type: "metrics",
          title: "Selected Metrics",
          datasetId,
          datasetRole: "portfolio_metrics",
          mappings: { y: [] },
        },
        {
          id: makeChartId(),
          type: "table",
          title: "Fold Summary",
          datasetId,
          datasetRole: "fold_summary",
          mappings: { y: [] },
        },
        {
          id: makeChartId(),
          type: "scatter2d",
          title: "Trial Objective",
          datasetId,
          datasetRole: "trials",
          mappings: { x: "number", y: ["value"] },
        },
        {
          id: makeChartId(),
          type: "table",
          title: "Optimization Trials",
          datasetId,
          datasetRole: "trials",
          mappings: { y: [] },
          maxRows: 100000,
        },
      ]);
      return;
    }
    setLayoutName("Data QA");
    setCharts([
      { ...defaultChartConfig(datasetId), title: "OHLC" },
      {
        id: makeChartId(),
        type: "timeseries",
        title: "Volume",
        datasetId,
        mappings: { x: "date", y: ["volume"] },
      },
      {
        id: makeChartId(),
        type: "table",
        title: "Rows",
        datasetId,
        mappings: { y: editableRecord?.columns.slice(0, 8) ?? [] },
      },
    ]);
  }

  function renderChartSettings(chart: ChartConfig) {
    return (
      <>
        <label className="field">
          <span>Title</span>
          <input value={chart.title} onChange={(event) => updateChart(chart.id, { title: event.target.value })} />
        </label>
        <label className="field">
          <span>Type</span>
          <select value={chart.type} onChange={(event) => updateChart(chart.id, { type: event.target.value as ChartType })}>
            <option value="ohlc">OHLC</option>
            <option value="timeseries">Time Series</option>
            <option value="scatter2d">2D Scatter</option>
            <option value="scatter3d">3D Scatter</option>
            <option value="table">Table</option>
            <option value="metrics">Metrics</option>
            <option value="text">Text</option>
            <option value="calculator">Calculator</option>
          </select>
        </label>
        {chart.type === "text" ? (
          <label className="field">
            <span>Text Artifact</span>
            <select value={chart.artifactId ?? ""} onChange={(event) => updateChart(chart.id, { artifactId: event.target.value || null })}>
              <option value="">None</option>
              {(store?.artifacts ?? [])
                .filter((artifact) => ["text", "raw_file"].includes(artifact.role) || ["text", "file"].includes(artifact.artifact_type))
                .map((artifact) => (
                  <option key={artifact.id} value={artifact.id}>
                    {artifact.name}
                  </option>
                ))}
            </select>
          </label>
        ) : (
          <>
            <label className="field">
              <span>Collection</span>
              <select
                value={chart.collectionId ?? ""}
                onChange={(event) =>
                  updateChart(chart.id, {
                    collectionId: event.target.value || null,
                    collectionIndex: 0,
                    collectionMode: chart.collectionMode ?? "selected",
                    datasetRole: event.target.value ? "fixed" : chart.datasetRole ?? "fixed",
                  })
                }
              >
                <option value="">None - use a fixed dataset or run role</option>
                {collectionArtifacts.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}
                  </option>
                ))}
              </select>
            </label>
            {chart.collectionId ? (
              <>
                <label className="field">
                  <span>Members</span>
                  <select value={chart.collectionMode ?? "selected"} onChange={(event) => updateChart(chart.id, { collectionMode: event.target.value as "selected" | "all" })}>
                    <option value="selected">Single member from active context</option>
                    <option value="all">All members in active context</option>
                  </select>
                </label>
                {(chart.collectionMode ?? "selected") === "selected" ? (
                  <label className="field">
                    <span>Active Member</span>
                    <select value={String(chart.collectionIndex ?? 0)} onChange={(event) => updateChart(chart.id, { collectionIndex: Number.parseInt(event.target.value, 10) || 0 })}>
                      {filterCollectionLeaves(
                        collectionLeafRecords(collectionArtifacts.find((collection) => collection.id === chart.collectionId)),
                        activeFold,
                        activeSplit,
                      ).map((leaf, index) => (
                        <option key={leaf.record.id} value={index}>
                          {leaf.path.slice(1).join(" / ") || leaf.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="empty compact-empty">
                    Plotting {filterCollectionLeaves(
                      collectionLeafRecords(collectionArtifacts.find((collection) => collection.id === chart.collectionId)),
                      activeFold,
                      activeSplit,
                    ).length} member(s) from the active Fold/Split controls.
                  </div>
                )}
                <div className="context-hint">Use the Fold and Split selectors above the canvas to filter collection-backed charts.</div>
              </>
            ) : (
              <>
                <label className="field">
                  <span>Fixed Dataset / Run Role</span>
                  <select
                    value={chart.datasetRole ?? "fixed"}
                    onChange={(event) => updateChart(chart.id, { datasetRole: event.target.value as ChartDatasetRole })}
                  >
                    {chartRoleOptions(chart.type).map((role) => (
                      <option key={role.value} value={role.value}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                </label>
                {(chart.datasetRole ?? "fixed") === "fixed" ? (
                  <label className="field">
                    <span>Dataset</span>
                    <select value={chart.datasetId ?? ""} onChange={(event) => updateChart(chart.id, { datasetId: event.target.value || null })}>
                      <option value="">None</option>
                      {topLevelRecords.map((record) => (
                        <option key={record.id} value={record.id}>
                          {record.label || record.name}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="empty compact-empty">
                    Showing: {store?.records.find((record) => record.id === resolveChartDatasetId(chart))?.label ?? "No matching data for the selected run"}
                  </div>
                )}
              </>
            )}
            <label className="field">
              <span>Max Rows</span>
              <input
                type="number"
                min="100"
                max="100000"
                value={chart.maxRows ?? 100000}
                onChange={(event) => updateChart(chart.id, { maxRows: Number.parseInt(event.target.value, 10) || 100000 })}
              />
            </label>
            <button
              disabled={!resolveChartDatasetId(chart)}
              onClick={() => {
                const sourceId = resolveChartDatasetId(chart);
                if (!sourceId) return;
                addChart("calculator", sourceId);
                setEditingChartId(null);
              }}
            >
              <Calculator size={16} /> Add Calculator
            </button>
          </>
        )}

        {chart.type === "ohlc" && (
          <>
            <label className="field">
              <span>Signal Source</span>
              <select
                value={chart.signalDatasetRole ?? "fixed"}
                onChange={(event) => updateChart(chart.id, { signalDatasetRole: event.target.value as ChartDatasetRole })}
              >
                {chartDatasetRoles
                  .filter((role) => ["fixed", "signals", "events"].includes(role.value))
                  .map((role) => (
                    <option key={role.value} value={role.value}>
                      {role.label}
                    </option>
                ))}
              </select>
            </label>
            {(chart.signalDatasetRole ?? "fixed") === "fixed" ? (
              <label className="field">
                <span>Signal Overlay</span>
                <select value={chart.signalDatasetId ?? ""} onChange={(event) => updateChart(chart.id, { signalDatasetId: event.target.value || null })}>
                  <option value="">None</option>
                  {topLevelRecords
                    .filter((record) => record.columns.includes("action") || record.columns.includes("signal"))
                    .map((record) => (
                      <option key={record.id} value={record.id}>
                        {record.label || record.name}
                      </option>
                    ))}
                </select>
              </label>
            ) : (
              <div className="empty compact-empty">
                Signals: {store?.records.find((record) => record.id === resolveSignalDatasetId(chart))?.label ?? "No matching signal artifact for the selected run/fold/split"}
              </div>
            )}
            {(["open", "high", "low", "close"] as const).map((key) => (
              <label className="field" key={key}>
                <span>{key}</span>
                <select value={chart.mappings[key] ?? key} onChange={(event) => updateChartMappings(chart.id, { [key]: event.target.value })}>
                  {editableColumns.map((column) => (
                    <option key={column}>{column}</option>
                  ))}
                </select>
              </label>
            ))}
            <div className="field">
              <span>Line Overlays</span>
              {(() => {
                const candleColumns = new Set([
                  chart.mappings.open ?? "open",
                  chart.mappings.high ?? "high",
                  chart.mappings.low ?? "low",
                  chart.mappings.close ?? "close",
                  "open",
                  "high",
                  "low",
                  "close",
                  "volume",
                ]);
                const options = editableNumericColumns.filter((column) => !candleColumns.has(column));
                return (
                  <>
                    <select
                      multiple
                      className="column-select compact-select"
                      value={chart.mappings.y ?? []}
                      onChange={(event) =>
                        setChartColumns(
                          chart,
                          Array.from(event.currentTarget.selectedOptions).map((option) => option.value),
                        )
                      }
                    >
                      {options.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                    <div className="button-row compact">
                      <button type="button" onClick={() => setChartColumns(chart, options.slice(0, 4))}>
                        Auto
                      </button>
                      <button type="button" onClick={() => setChartColumns(chart, [])}>
                        Clear
                      </button>
                    </div>
                    {options.length === 0 && <div className="empty compact-empty">No derived numeric columns available.</div>}
                  </>
                );
              })()}
            </div>
          </>
        )}

        {(chart.type === "timeseries" || chart.type === "table" || chart.type === "metrics") && (
          <div className="field">
            <span>Columns</span>
            {(() => {
              const options = chart.type === "table" ? editableColumns : editableNumericColumns;
              return (
                <>
                  <select
                    multiple
                    className="column-select"
                    value={chart.mappings.y ?? []}
                    onChange={(event) =>
                      setChartColumns(
                        chart,
                        Array.from(event.currentTarget.selectedOptions).map((option) => option.value),
                      )
                    }
                  >
                    {options.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                  <div className="button-row compact">
                    <button type="button" onClick={() => setChartColumns(chart, options.slice(0, chart.type === "metrics" ? 12 : 6))}>
                      Auto
                    </button>
                    <button type="button" onClick={() => setChartColumns(chart, [])}>
                      Clear
                    </button>
                  </div>
                  {options.length === 0 && <div className="empty compact-empty">No selectable columns.</div>}
                </>
              );
            })()}
          </div>
        )}

        {(chart.type === "scatter2d" || chart.type === "scatter3d") && (
          <>
            <label className="field">
              <span>X</span>
              <select value={chart.mappings.x ?? ""} onChange={(event) => updateChartMappings(chart.id, { x: event.target.value })}>
                {editableNumericColumns.map((column) => (
                  <option key={column}>{column}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Y</span>
              <select value={chart.mappings.y?.[0] ?? ""} onChange={(event) => updateChartMappings(chart.id, { y: [event.target.value] })}>
                {editableNumericColumns.map((column) => (
                  <option key={column}>{column}</option>
                ))}
              </select>
            </label>
            {chart.type === "scatter3d" && (
              <label className="field">
                <span>Z</span>
                <select value={chart.mappings.z ?? ""} onChange={(event) => updateChartMappings(chart.id, { z: event.target.value })}>
                  {editableNumericColumns.map((column) => (
                    <option key={column}>{column}</option>
                  ))}
                </select>
              </label>
            )}
          </>
        )}
      </>
    );
  }

  function renderSidebarTab(id: string, label: string) {
    const active = activePage === id;
    return (
      <button
        className={active ? "sidebar-tab active" : "sidebar-tab"}
        onClick={() => setActivePage(active ? "" : id)}
        aria-expanded={active}
        type="button"
      >
        <span>{label}</span>
        <ChevronDown size={16} />
      </button>
    );
  }

  function renderDataStoreModal() {
    return (
      <div className="store-modal-grid">
        <div className="artifact-inspector">
          <h3>
            <Sparkles size={16} /> Selected Artifact
          </h3>
          {selected ? (
            <div className="details">
              <p>
                <strong>{selected.name}</strong>
              </p>
              <p>Label: {selected.label}</p>
              <p>Kind: {selected.kind}</p>
              {coverageWarning(selected) && <p className="warning-text">{coverageWarning(selected)}</p>}
              <p>Columns: {selected.columns.join(", ")}</p>
              <pre>{JSON.stringify(selected.attrs, null, 2)}</pre>
              <div className="button-row compact">
                <button onClick={() => addRecordToCanvas(selected)}>
                  <BarChart3 size={16} /> Add View
                </button>
                <button onClick={() => addRecordToCanvas(selected, "table")}>
                  Table
                </button>
                {(selected.columns.includes("action") || selected.columns.includes("signal")) && (
                  <button onClick={() => overlayRecordOnOhlc(selected)}>
                    Overlay Signals
                  </button>
                )}
              </div>
              <button
                className="danger-button"
                disabled={busy}
                onClick={() => runAction(deleteSelectedRecord)}
              >
                <Trash2 size={16} /> Delete Artifact
              </button>
            </div>
          ) : (
            <div className="empty">No artifact selected.</div>
          )}
        </div>

        <div className="store-browser">
          <div className="store-grid">
            <div>
              <h3>Data</h3>
              {topLevelNavigation.length === 0 ? (
                <div className="empty">Add or fetch data to start.</div>
              ) : (
                topLevelNavigation.map((node) => renderNode(node))
              )}
            </div>
            <div>
              <h3>Workflow Configs</h3>
              {workspaceModel?.transforms.map((transformSet) => (
                <div className="study-row" key={transformSet.id}>
                  <strong>{transformSet.name}</strong>
                  <span>{transformSet.transforms.length} transform(s)</span>
                </div>
              ))}
              {workspaceModel?.strategies.map((strategy) => (
                <div className="study-row" key={strategy.id}>
                  <strong>{strategy.name}</strong>
                  <span>
                    Template: {strategy.signals.length + strategy.orders.length} instruction(s)
                  </span>
                </div>
              ))}
              {workspaceModel?.simulations.map((simulation) => (
                <div className="study-row" key={simulation.id}>
                  <strong>{simulation.name}</strong>
                  <span>Runner: {simulation.simulation.function}</span>
                </div>
              ))}
            </div>
            <div>
              <h3>Studies</h3>
              {studyRuns.length === 0 ? (
                <div className="empty">No studies yet.</div>
              ) : (
                studyRuns.map((run) => (
                  <div className="study-row" key={run.run_id}>
                    <strong>{run.label}</strong>
                    <span>{run.folds.length || 1} fold(s)</span>
                  </div>
                ))
              )}
            </div>
            <div>
              <h3>Collections</h3>
              {collectionArtifacts.length === 0 ? (
                <div className="empty">No collections yet.</div>
              ) : (
                collectionArtifacts.slice().reverse().map((artifact) => {
                  const members = artifactMembers(artifact);
                  return (
                    <div className="study-row" key={artifact.id}>
                      <strong>{artifact.name}</strong>
                      <span>
                        {artifact.role} · {members.length} member(s)
                      </span>
                      <div className="button-row compact">
                        <button onClick={() => setSelectedCollectionId(artifact.id)}>Inspect</button>
                        <button onClick={() => addCollectionToCanvas(artifact, "selected")}>Plot</button>
                        <button onClick={() => addCollectionToCanvas(artifact, "all")}>Plot All</button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
            <div>
              <h3>Standalone Files</h3>
              {!topLevelFileArtifacts.length ? (
                <div className="empty">No standalone file artifacts.</div>
              ) : (
                topLevelFileArtifacts.slice(-12).reverse().map((artifact) => (
                  <div className="study-row" key={artifact.id}>
                    <strong>{artifact.name}</strong>
                    <span>
                      {artifact.role} · {artifact.artifact_type}
                      {artifact.dataframe_id ? " · table registered" : ""}
                    </span>
                    {(artifact.role === "text" || artifact.role === "raw_file" || artifact.artifact_type === "text") && (
                      <button onClick={() => addArtifactToCanvas(artifact)}>View</button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
          {selectedCollection ? (
            (() => {
              const leaves = collectionLeafRecords(selectedCollection);
              const filteredLeaves = filterCollectionLeaves(leaves, activeFold, activeSplit);
              const summary = collectionLeafSummary(leaves);
              const filteredSummary = collectionLeafSummary(filteredLeaves);
              return (
                <div className="collection-browser">
                  <div className="collection-heading">
                    <div>
                      <h3>{selectedCollection.name}</h3>
                      <span>
                        {selectedCollection.role} · {summary.leaves} plottable member(s)
                      </span>
                    </div>
                    <div className="button-row compact">
                      <button onClick={() => setPrepareSourceId(selectedCollection.id)}>Use as Prepare Source</button>
                      <button onClick={() => addCollectionToCanvas(selectedCollection, "selected")}>Plot Selected</button>
                      <button onClick={() => addCollectionToCanvas(selectedCollection, "all")}>Plot Active Context</button>
                    </div>
                  </div>
                  <div className="collection-stats">
                    <div>
                      <span>Members</span>
                      <strong>{summary.leaves}</strong>
                    </div>
                    <div>
                      <span>Samples</span>
                      <strong>{summary.samples || "-"}</strong>
                    </div>
                    <div>
                      <span>Folds</span>
                      <strong>{summary.folds || "-"}</strong>
                    </div>
                    <div>
                      <span>Splits</span>
                      <strong>{summary.splits.join(", ") || "-"}</strong>
                    </div>
                    <div>
                      <span>Rows</span>
                      <strong>{summary.rows.toLocaleString()}</strong>
                    </div>
                    <div>
                      <span>Columns</span>
                      <strong>{summary.columns}</strong>
                    </div>
                  </div>
                  <div className="context-hint">
                    Active canvas context: Fold {activeFold === "all" ? "All" : activeFold}, Split {activeSplit}. Matching members: {filteredSummary.leaves}.
                  </div>
                  <div className="collection-leaf-list compact-list">
                    {filteredLeaves.length === 0 ? (
                      <div className="empty">No members match the active Fold/Split controls.</div>
                    ) : (
                      filteredLeaves.slice(0, 12).map(({ label, record, path }) => (
                        <div className="collection-leaf" key={`${selectedCollection.id}-${record.id}`}>
                          <div>
                            <strong>{path.slice(1).join(" / ") || label}</strong>
                            <small>
                              {record.shape[0].toLocaleString()} x {record.shape[1]} · {record.columns.slice(0, 8).join(", ")}
                            </small>
                          </div>
                        </div>
                      ))
                    )}
                    {filteredLeaves.length > 12 && (
                      <div className="context-hint">Showing 12 of {filteredLeaves.length} matching members. Plot the collection to inspect them interactively.</div>
                    )}
                  </div>
                </div>
              );
            })()
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      {editableChart && editingChartId && (
        <div className="modal-backdrop" onMouseDown={() => setEditingChartId(null)}>
          <div className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <strong>Chart Settings</strong>
                <span>{editableChart.title}</span>
              </div>
              <button className="icon-button" onClick={() => setEditingChartId(null)}>
                x
              </button>
            </div>
            <div className="modal-body">{renderChartSettings(editableChart)}</div>
          </div>
        </div>
      )}
      {settingsOpen && (
        <div className="modal-backdrop" onMouseDown={() => setSettingsOpen(false)}>
          <div className="modal small-modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <strong>User Settings</strong>
                <span>Provider credentials</span>
              </div>
              <button className="icon-button" onClick={() => setSettingsOpen(false)}>
                x
              </button>
            </div>
            <div className="modal-body">
              <label className="field">
                <span>FMP API Key</span>
                <input value={providerKey} onChange={(event) => setProviderKey(event.target.value)} type="password" />
              </label>
              <button disabled={!providerKey || !workspaceId} onClick={() => runAction(saveProviderKey)}>
                <KeyRound size={16} /> Save Key
              </button>
            </div>
          </div>
        </div>
      )}
      {layoutDialogOpen && (
        <div className="modal-backdrop" onMouseDown={() => setLayoutDialogOpen(false)}>
          <div className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <strong>Chart Layouts</strong>
                <span>Templates and saved layouts</span>
              </div>
              <button className="icon-button" onClick={() => setLayoutDialogOpen(false)}>
                x
              </button>
            </div>
            <div className="modal-body">
              <label className="field">
                <span>Name</span>
                <input value={layoutName} onChange={(event) => setLayoutName(event.target.value)} />
              </label>
              <div className="button-row compact">
                <button onClick={saveLayout}>Save Layout</button>
                <button onClick={() => applyTemplate("review")}>Execution</button>
                <button onClick={() => applyTemplate("optimization")}>Optimize</button>
                <button onClick={() => applyTemplate("data")}>Data QA</button>
              </div>
              {savedLayouts.length > 0 && (
                <label className="field">
                  <span>Saved Layout</span>
                  <select
                    value=""
                    onChange={(event) => {
                      const layout = savedLayouts.find((item) => item.id === event.target.value);
                      if (layout) {
                        loadLayout(layout);
                        setLayoutDialogOpen(false);
                      }
                    }}
                  >
                    <option value="">Load layout</option>
                    {savedLayouts.map((layout) => (
                      <option key={layout.id} value={layout.id}>
                        {layout.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </div>
        </div>
      )}
      {dataStoreOpen && (
        <div className="modal-backdrop" onMouseDown={() => setDataStoreOpen(false)}>
          <div className="modal store-modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <strong>Data Store</strong>
                <span>Artifacts, components, studies, and metadata</span>
              </div>
              <button className="icon-button" onClick={() => setDataStoreOpen(false)}>
                x
              </button>
            </div>
            <div className="modal-body">{renderDataStoreModal()}</div>
          </div>
        </div>
      )}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-main">
            <Activity size={22} />
            <div>
              <strong>Quantapy</strong>
              <span>Workbench</span>
            </div>
          </div>
          <div className="brand-actions">
            <button className="icon-button" onClick={() => setDataStoreOpen(true)} title="Data store">
              <Database size={17} />
            </button>
            <button className="icon-button" onClick={() => setLayoutDialogOpen(true)} title="Chart layouts">
              <Columns3 size={17} />
            </button>
            <button className="icon-button" onClick={() => setSettingsOpen(true)} title="Settings">
              <Settings size={17} />
            </button>
          </div>
        </div>

        <div className="sidebar-accordion">
        {renderSidebarTab("data", "Data")}
        <div className={activePage === "data" ? "task-page active" : "task-page"}>
        <div className="form-block">
          <h3>Data Source</h3>
          <label className="field">
            <span>Category</span>
            <select value={dataCategory} onChange={(event) => setDataCategory(event.target.value)}>
              {Object.keys(components)
                .filter((category) => !["Technical", "Signal", "Order", "Simulation", "Evaluate", "Validation", "Best Trial", "Optimization"].includes(category))
                .sort()
                .map((category) => (
                  <option key={category}>{category}</option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>Function</span>
            <select value={dataFunction} onChange={(event) => setDataFunction(event.target.value)}>
              {dataFunctionOptions.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Source</span>
            <select value={dataSource} onChange={(event) => setDataSource(event.target.value)}>
              {dataSourceOptions.map((source) => (
                <option key={source}>{source}</option>
              ))}
            </select>
          </label>
          {renderSchemaFields(dataSchema, dataParams, (key, value) =>
            setDataParams((current) => ({ ...current, [key]: value })),
            ["api_key"],
          )}
        <button
          disabled={dataSource === "FMP" && !providerKey}
          onClick={() =>
            runAction(async () => {
              if (!workspaceId) return;
              const summary = await api<StoreSummary>(`/workspaces/${workspaceId}/data/fetch`, {
                method: "POST",
	                body: JSON.stringify({
	                  category: dataCategory,
	                  function: dataFunction,
	                  source: dataSource,
	                  params: dataParams,
	                }),
              });
              setStore(summary);
              const rawCollection = latestCollection(summary, "raw_data");
              if (rawCollection) {
                setSelectedCollectionId(rawCollection.id);
                setPrepareSourceId(rawCollection.id);
                setWorkingCollectionId(rawCollection.id);
              }
              showDatasetView(summary, latestRawId(summary));
              setError(latestFetchWarning(summary));
            })
          }
        >
          <Database size={16} /> Fetch Data
        </button>
        </div>

        <div className="form-block">
          <h3>Prepare Collections</h3>
          <label className="field">
            <span>Source</span>
            <select value={prepareSourceId} onChange={(event) => setPrepareSourceId(event.target.value)}>
              {prepareSourceOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
            {prepareSourceOptions.find((option) => option.id === prepareSourceId)?.detail ? (
              <small>{prepareSourceOptions.find((option) => option.id === prepareSourceId)?.detail}</small>
            ) : null}
          </label>
          <div className="field-row">
            <label className="field">
              <span>Samples</span>
              <input type="number" min="1" max="5000" value={noiseCount} onChange={(event) => setNoiseCount(Number.parseInt(event.target.value, 10) || 1)} />
            </label>
            <label className="field">
              <span>Noise Std</span>
              <input type="number" step="0.001" value={noiseStddev} onChange={(event) => setNoiseStddev(Number.parseFloat(event.target.value) || 0)} />
            </label>
          </div>
          <button disabled={!prepareSourceId || busy} onClick={() => runAction(createNoiseCollection)}>
            <Sparkles size={16} /> Create Noise Collection
          </button>
          <label className="field">
            <span>Split Method</span>
            <select value={splitMethod} onChange={(event) => setSplitMethod(event.target.value)}>
              <option value="holdout">Holdout</option>
              <option value="walk_forward">Walk Forward</option>
            </select>
          </label>
          {splitMethod === "holdout" ? (
            <div className="field-row three">
              <label className="field">
                <span>Train</span>
                <input type="number" step="0.05" min="0" max="1" value={splitTrainRatio} onChange={(event) => setSplitTrainRatio(Number.parseFloat(event.target.value) || 0)} />
              </label>
              <label className="field">
                <span>Val</span>
                <input type="number" step="0.05" min="0" max="1" value={splitValRatio} onChange={(event) => setSplitValRatio(Number.parseFloat(event.target.value) || 0)} />
              </label>
              <label className="field">
                <span>Test</span>
                <input type="number" step="0.05" min="0" max="1" value={splitTestRatio} onChange={(event) => setSplitTestRatio(Number.parseFloat(event.target.value) || 0)} />
              </label>
            </div>
          ) : (
            <label className="field">
              <span>Folds</span>
              <input type="number" min="1" max="100" value={splitFolds} onChange={(event) => setSplitFolds(Number.parseInt(event.target.value, 10) || 1)} />
            </label>
          )}
          <button disabled={!prepareSourceId || busy} onClick={() => runAction(splitPrepareSource)}>
            <Columns3 size={16} /> Split Source
          </button>
          <label className="field">
            <span>Calculator Recipe</span>
            <select value={prepareRecipeId} onChange={(event) => setPrepareRecipeId(event.target.value)}>
              <option value="">No recipe</option>
              {calculatorRecipeRecords.map((record) => (
                <option key={record.id} value={record.id}>
                  {record.label || record.name}
                </option>
              ))}
            </select>
          </label>
          <button disabled={!prepareSourceId || !prepareRecipeId || busy} onClick={() => runAction(prepareCollectionWithCalculator)}>
            <Calculator size={16} /> Apply Calculator to Collection
          </button>
        </div>
        </div>

        <div className={activePage === "transforms" ? "task-page active" : "task-page"}>
        <div className="form-block">
          <h3>Indicator</h3>
          <label className="field">
            <span>Source Dataset</span>
            <select value={transformSourceRecord?.id ?? ""} onChange={(event) => setTransformDatasetId(event.target.value)}>
              {(store?.records ?? [])
                .filter((record) => ["raw", "derived"].includes(record.kind) && record.columns.some((column) => ["close", "open", "high", "low"].includes(column)))
                .map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.label || record.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>Function</span>
            <select value={indicatorFunction} onChange={(event) => setIndicatorFunction(event.target.value)}>
              {Object.keys(technical)
                .sort()
                .map((name) => (
                  <option key={name}>{name}</option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>Source</span>
            <select value={indicatorSource} onChange={(event) => setIndicatorSource(event.target.value)}>
              {Object.keys(technical[indicatorFunction] ?? {}).map((source) => (
                <option key={source}>{source}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Transform Name</span>
            <input value={indicatorName} onChange={(event) => setIndicatorName(event.target.value)} />
          </label>

          {Object.entries(indicatorSchema?.properties ?? {})
            .filter(([key]) => key !== "name" && key !== "output_names" && key !== "display")
            .slice(0, 8)
            .map(([key, schema]) => (
              <label className="field" key={key}>
                <span>{key}</span>
                {(schema.use_variable_options || ["real", "open", "high", "low", "close"].includes(key)) && transformSourceColumns.length ? (
                  <select
                    value={String(indicatorParams[key] ?? schema.default ?? "")}
                    onChange={(event) => setIndicatorInputParam(key, event.target.value)}
                  >
                    {transformSourceColumns.map((column) => (
                      <option key={column}>{column}</option>
                    ))}
                  </select>
                ) : schema.enum ? (
                  <select
                    value={String(indicatorParams[key] ?? "")}
                    onChange={(event) => setParam(key, coerceParam(schema, event.target.value))}
                  >
                    {schema.enum.map((option) => (
                      <option key={String(option)} value={String(option)}>
                        {String(option)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={String(indicatorParams[key] ?? "")}
                    type={schema.type === "integer" || schema.type === "number" ? "number" : "text"}
                    onChange={(event) =>
                      setParam(
                        key,
                        schema.type === "integer"
                          ? Number.parseInt(event.target.value, 10)
                          : schema.type === "number"
                            ? Number.parseFloat(event.target.value)
                            : event.target.value,
                      )
                    }
                  />
                )}
              </label>
            ))}

          {Object.keys((indicatorParams.output_names as Record<string, string>) ?? {}).map((key) => (
            <label className="field" key={key}>
              <span>Output {key}</span>
              <input
                value={String((indicatorParams.output_names as Record<string, string>)[key])}
                onChange={(event) => setOutputParam(key, event.target.value)}
              />
            </label>
          ))}
        </div>

        <button
          disabled={!transformSourceRecord}
          onClick={() =>
            runAction(async () => {
              if (!workspaceId || !transformSourceRecord) return;
              await api(`/workspaces/${workspaceId}/calculator/transforms`, {
                method: "POST",
                body: JSON.stringify({
                  function: indicatorFunction,
                  source: indicatorSource,
                  name: indicatorName,
                  params: indicatorParams,
                }),
              });
              const result = await api<{ store: StoreSummary; record: StoreRecord }>(`/workspaces/${workspaceId}/calculator/derive`, {
                method: "POST",
                body: JSON.stringify({ dataset_id: transformSourceRecord.id, name: `${transformSourceRecord.name}-${indicatorName}` }),
              });
              setStore(result.store);
              setSelectedId(result.record.id);
              setTransformDatasetId(result.record.id);
              setBacktestDatasetId(result.record.id);
              setOptimizeDatasetId(result.record.id);
              setCharts((current) =>
                current.map((chart) =>
                  chart.datasetId === transformSourceRecord.id
                    ? {
                        ...chart,
                        datasetId: result.record.id,
                        mappings: {
                          ...chart.mappings,
                          y:
                            chart.type === "table"
                              ? result.record.columns.slice(0, 10)
                              : [...new Set([...(chart.mappings.y ?? []), ...Object.values(indicatorParams.output_names as Record<string, string>)])],
                        },
                      }
                    : chart,
                ),
              );
            })
          }
        >
          <LineChart size={16} /> Add + Derive Indicator
        </button>
        </div>

        {renderSidebarTab("strategy", "Configure")}
        <div className={activePage === "strategy" ? "task-page active" : "task-page"}>
        <div className="form-block">
          <h3>Execution Template</h3>
          <label className="field">
            <span>Working Collection</span>
            <select
              value={configuredWorkingCollection?.id ?? ""}
              onChange={(event) => {
                setWorkingCollectionId(event.target.value);
                setSelectedCollectionId(event.target.value);
              }}
            >
              <option value="">Use latest prepared collection</option>
              {collectionArtifacts.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          </label>
          <div className="empty compact-empty">
            Active input: {backtestDatasetRecord?.label || backtestDatasetRecord?.name || "No matching member"} · Fold {activeFold === "all" ? "All" : activeFold}, Split {activeSplit}
          </div>
          <label className="field">
            <span>Simulation Plugin</span>
            <select value={selectedRunner} onChange={(event) => setSelectedRunner(event.target.value)}>
              {executorOptions.map((executor) => (
                <option key={executor.runner} value={executor.runner}>
                  {executor.label ?? executor.runner}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Template Name</span>
            <input value={strategyName} onChange={(event) => setStrategyName(event.target.value)} />
          </label>
          {executorSections.some((section) => section.component_category) ? (
            <>
              <label className="field">
                <span>Configuration Section</span>
                <select value={strategyComponentCategory} onChange={(event) => setStrategyComponentCategory(event.target.value)}>
                  {executorSections.filter((section) => section.component_category).map((section) => (
                    <option key={section.key} value={section.key}>
                      {section.label}
                    </option>
                  ))}
                </select>
              </label>
              {activeTemplateSection && activeTemplateSection.component_category ? (
                <>
                  <label className="field">
                    <span>Registered Function</span>
                    <select
                      value={activeTemplateFunction}
                      onChange={(event) => {
                        const nextFunction = event.target.value;
                        const sources = Object.keys(activeTemplateComponents[nextFunction] ?? {}).sort();
                        const nextSource = sources.includes(activeTemplateSource) ? activeTemplateSource : sources[0] ?? "Internal";
                        updateTemplateSection(activeTemplateSection.key, {
                          function: nextFunction,
                          source: nextSource,
                          params: defaultsFor(activeTemplateComponents[nextFunction]?.[nextSource]),
                        });
                      }}
                    >
                      {Object.keys(activeTemplateComponents).sort().map((name) => (
                        <option key={name}>{name}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Source</span>
                    <select
                      value={activeTemplateSource}
                      onChange={(event) => {
                        const nextSource = event.target.value;
                        updateTemplateSection(activeTemplateSection.key, {
                          source: nextSource,
                          params: defaultsFor(activeTemplateComponents[activeTemplateFunction]?.[nextSource]),
                        });
                      }}
                    >
                      {Object.keys(activeTemplateComponents[activeTemplateFunction] ?? {}).map((source) => (
                        <option key={source}>{source}</option>
                      ))}
                    </select>
                  </label>
                  {renderSchemaFields(activeTemplateSchema, activeTemplateState?.params ?? {}, (key, value) =>
                    updateTemplateSectionParam(activeTemplateSection.key, key, value),
                    undefined,
                    activeTemplateSection.column_options ? backtestColumnOptions : [],
                  )}
                  {activeTemplateSection.multiple ? (
                    <button onClick={() => addTemplateSectionItem(activeTemplateSection)}>Add Instruction</button>
                  ) : null}
                </>
              ) : null}
            </>
          ) : selectedExecutorSchema ? (
            <>
              {renderSchemaFields(selectedExecutorSchema, executorConfig, (key, value) =>
                setExecutorConfig((current) => ({ ...current, [key]: value })),
                [],
                backtestColumnOptions,
              )}
            </>
          ) : (
            <div className="empty compact-empty">This executor has not registered a structured template editor.</div>
          )}
          <div className="component-list">
            {executorSections.filter((section) => section.component_category).flatMap((section) => {
              const state = templateSections[section.key];
              const items = section.multiple
                ? state?.items ?? []
                : currentTemplateComponent(section)
                  ? [currentTemplateComponent(section) as ComponentSpec]
                  : [];
              return items.map((item, index) => (
                <div className="component-card" key={`${section.key}-${index}`}>
                  <div>
                    <strong>{item.function}</strong>
                    <span>{section.label}</span>
                  </div>
                  <p>{Object.entries(item.params).map(([key, value]) => `${key}: ${String(value)}`).join(" | ")}</p>
                  {section.multiple ? (
                    <button onClick={() => removeTemplateSectionItem(section.key, index)}>Remove</button>
                  ) : null}
                </div>
              ));
            })}
          </div>
          <button
            disabled={!workspaceId || !selectedExecutor}
            onClick={() =>
              runAction(async () => {
                if (!workspaceId) return;
                const sections = buildExecutionTemplateSections();
                setStrategySignals((sections["strategy.signals"] as ComponentSpec[]) ?? []);
                setStrategyOrders((sections["strategy.orders"] as ComponentSpec[]) ?? []);
                const result = await api<{ store: StoreSummary }>(`/workspaces/${workspaceId}/execution-templates`, {
                  method: "POST",
                  body: JSON.stringify({ name: strategyName, runner: selectedRunner, sections, config: executorConfig }),
                });
                setStore(result.store);
              })
            }
          >
            Save Template
          </button>
        </div>
        </div>

        {renderSidebarTab("backtest", "Execute")}
        <div className={activePage === "backtest" ? "task-page active" : "task-page"}>
        <div className="form-block">
          <h3>Execution</h3>
          <label className="field">
            <span>Input Collection</span>
            <select
              value={configuredWorkingCollection?.id ?? ""}
              onChange={(event) => {
                setWorkingCollectionId(event.target.value);
                setSelectedCollectionId(event.target.value);
              }}
            >
              <option value="">Use latest prepared collection</option>
              {collectionArtifacts.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          </label>
          <div className="empty compact-empty">
            Running active member: {backtestDatasetRecord?.label || backtestDatasetRecord?.name || "No matching member"}. Use the canvas Fold/Split controls to change the active member.
          </div>
          <label className="field">
            <span>Runtime</span>
            <select value="local" disabled>
              <option value="local">Local Python</option>
            </select>
          </label>
          <div className="empty compact-empty">Simulation-specific parameters live in Configure. Execute only runs the saved template locally.</div>
        </div>

        <button
          disabled={!backtestDatasetRecord || (isTradingRunner && !hasSavedStrategy)}
          onClick={() =>
            runAction(async () => {
              if (!workspaceId || !backtestDatasetRecord) return;
              const result = await api<{ store: StoreSummary; run_id?: string }>(
                `/workspaces/${workspaceId}/execute`,
                {
                  method: "POST",
                  body: JSON.stringify({
                    dataset_id: backtestDatasetRecord.id,
                    runner: selectedRunner,
                    template_id: workspaceModel?.active?.execution_template_id,
                    executor_config: executorConfig,
                  }),
                },
              );
              setStore(result.store);
              if (result.run_id) {
                setActiveRunId(result.run_id);
                setActiveFold("all");
              }
              applyExecutionReview(result.store, result.run_id, backtestDatasetRecord.id);
            })
          }
        >
          <Play size={16} /> Run Execution
        </button>
        {isTradingRunner && !hasSavedStrategy && <div className="empty compact-empty">Save an execution template before running the selected runner.</div>}
        </div>

        {renderSidebarTab("evaluate", "Evaluate")}
        <div className={activePage === "evaluate" ? "task-page active" : "task-page"}>
        <div className="form-block">
          <h3>Evaluation</h3>
          <label className="field">
            <span>Source Run</span>
            <select value={activeRunId} onChange={(event) => setActiveRunId(event.target.value)}>
              <option value="">Latest execution run</option>
              {(workspaceModel?.executions?.runs ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  {run.runner ?? "run"} · {run.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Evaluator</span>
            <select value={selectedEvaluator} onChange={(event) => setSelectedEvaluator(event.target.value)}>
              {evaluatorOptions.map((evaluator) => (
                <option key={evaluator.evaluator} value={evaluator.evaluator}>
                  {evaluator.label ?? evaluator.evaluator}
                </option>
              ))}
            </select>
          </label>
          {renderSchemaFields(activeEvaluatorSchema, evaluatorConfig, (key, value) =>
            setEvaluatorConfig((current) => ({ ...current, [key]: value })),
            [],
          )}
          <button
            disabled={!workspaceId || !selectedEvaluator}
            onClick={() =>
              runAction(async () => {
                if (!workspaceId) return;
                const result = await api<{ store: StoreSummary; evaluation_run_id?: string }>(`/workspaces/${workspaceId}/evaluate`, {
                  method: "POST",
                  body: JSON.stringify({
                    evaluator: selectedEvaluator,
                    run_id: activeRunId || undefined,
                    config: evaluatorConfig,
                  }),
                });
                setStore(result.store);
                applyExecutionReview(result.store, activeRunId || result.store.latest_run_id);
              })
            }
          >
            <Sparkles size={16} /> Run Evaluation
          </button>
          <div className="empty compact-empty">Evaluator inputs are auto-bound from artifacts produced by the selected run.</div>
        </div>
        </div>

        {renderSidebarTab("optimize", "Optimize")}
        <div className={activePage === "optimize" ? "task-page active" : "task-page"}>
        <div className="form-block">
          <h3>Optimization</h3>
          <label className="field">
            <span>Study Collection</span>
            <select
              value={configuredWorkingCollection?.id ?? ""}
              onChange={(event) => {
                setWorkingCollectionId(event.target.value);
                setSelectedCollectionId(event.target.value);
              }}
            >
              <option value="">Use latest prepared collection</option>
              {collectionArtifacts.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
                ))}
            </select>
          </label>
          <div className="empty compact-empty">
            Active study input: {optimizeDatasetRecord?.label || optimizeDatasetRecord?.name || "No matching member"}.
          </div>
          <h3>Validation Plan</h3>
          <label className="field">
            <span>Validation Method</span>
            <select value={validationFunction} onChange={(event) => setValidationFunction(event.target.value)}>
              {Object.keys(validationComponents).sort().map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Validation Source</span>
            <select value={validationSource} onChange={(event) => setValidationSource(event.target.value)}>
              {Object.keys(validationComponents[validationFunction] ?? {}).map((source) => (
                <option key={source}>{source}</option>
              ))}
            </select>
          </label>
          {renderSchemaFields(validationSchema, validationParams, (key, value) =>
            setValidationParams((current) => ({ ...current, [key]: value })),
          )}
          <label className="field">
            <span>Best Trial Selection</span>
            <select value={bestTrialFunction} onChange={(event) => setBestTrialFunction(event.target.value)}>
              {Object.keys(bestTrialComponents).sort().map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Best Trial Source</span>
            <select value={bestTrialSource} onChange={(event) => setBestTrialSource(event.target.value)}>
              {Object.keys(bestTrialComponents[bestTrialFunction] ?? {}).map((source) => (
                <option key={source}>{source}</option>
              ))}
            </select>
          </label>
          {renderSchemaFields(bestTrialSchema, bestTrialParams, (key, value) =>
            setBestTrialParams((current) => ({ ...current, [key]: value })),
          )}
          <label className="field">
            <span>Optimizer</span>
            <select value={optimizerFunction} onChange={(event) => setOptimizerFunction(event.target.value)}>
              {Object.keys(optimizerComponents).sort().map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Optimizer Source</span>
            <select value={optimizerSource} onChange={(event) => setOptimizerSource(event.target.value)}>
              {Object.keys(optimizerComponents[optimizerFunction] ?? {}).map((source) => (
                <option key={source}>{source}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Trials</span>
            <input
              type="number"
              value={optimizationTrials}
              onChange={(event) => setOptimizationTrials(Number.parseInt(event.target.value, 10))}
            />
          </label>
          <label className="field">
            <span>Objectives</span>
            <input value={optimizationObjectives} onChange={(event) => setOptimizationObjectives(event.target.value)} />
          </label>
          <label className="field">
            <span>Target</span>
            <select
              value={newOptParam.target}
              onChange={(event) => {
                const target = event.target.value;
                setNewOptParam((current) => ({ ...current, target, name: "", index: target === "Transform" ? "" : "0" }));
              }}
            >
              {["Transform", "Signal", "Order", "Simulation"].map((target) => (
                <option key={target}>{target}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Component</span>
            {newOptParam.target === "Transform" ? (
              <select value={newOptParam.name} onChange={(event) => setNewOptField("name", event.target.value)}>
                <option value="">Select transform</option>
                {optSubjectOptions().map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            ) : (
              <select
                value={String(newOptParam.index)}
                onChange={(event) => setNewOptField("index", event.target.value.split(":")[0])}
              >
                {optSubjectOptions().map((option) => (
                  <option key={option} value={option.split(":")[0]}>
                    {option}
                  </option>
                ))}
              </select>
            )}
          </label>
          <label className="field">
            <span>Parameter</span>
            <input value={newOptParam.param} onChange={(event) => setNewOptField("param", event.target.value)} />
          </label>
          <label className="field">
            <span>Type</span>
            <select value={newOptParam.dtype} onChange={(event) => setNewOptField("dtype", event.target.value)}>
              <option>integer</option>
              <option>number</option>
            </select>
          </label>
          <div className="field-row">
            <label className="field">
              <span>Min</span>
              <input type="number" value={newOptParam.low} onChange={(event) => setNewOptField("low", Number.parseFloat(event.target.value))} />
            </label>
            <label className="field">
              <span>Max</span>
              <input type="number" value={newOptParam.high} onChange={(event) => setNewOptField("high", Number.parseFloat(event.target.value))} />
            </label>
          </div>
          <button onClick={addOptimizationParameter}>Add Optimization Parameter</button>
          <div className="param-list">
            {optParams.map((parameter, index) => (
              <div key={index} className="param-row">
                <span>{parameter.target}</span>
                <strong>{parameter.name || parameter.index || "index"}</strong>
                <span>{parameter.param}</span>
                <small>
                  {parameter.low}..{parameter.high}
                </small>
                <button onClick={() => setOptParams((current) => current.filter((_, i) => i !== index))}>Remove</button>
              </div>
            ))}
          </div>
        </div>

        <button
          disabled={!optimizeDatasetRecord}
          onClick={() =>
            runAction(async () => {
              if (!workspaceId || !optimizeDatasetRecord) return;
              const parameters = optParams.map((parameter) => ({
                ...parameter,
                index: parameter.index === "" ? null : Number.parseInt(String(parameter.index), 10),
              }));
              const result = await api<{ store: StoreSummary; run_id?: string }>(
                `/workspaces/${workspaceId}/study/optimize`,
                {
                  method: "POST",
                  body: JSON.stringify({
	                    dataset_id: optimizeDatasetRecord.id,
                      runner: selectedRunner,
	                    trials: optimizationTrials,
	                    objectives: optimizationObjectives.split(",").map((item) => item.trim()).filter(Boolean),
                    validation: {
                      category: "Validation",
                      function: validationFunction,
                      source: validationSource,
                      params: validationParams,
                    },
                    best_trial: {
                      category: "Best Trial",
                      function: bestTrialFunction,
                      source: bestTrialSource,
                      params: bestTrialParams,
                    },
                    optimizer: {
                      category: "Optimization",
                      function: optimizerFunction,
                      source: optimizerSource,
                      params: {},
                    },
	                    parameters,
	                  }),
                },
              );
              setStore(result.store);
              if (result.run_id) {
                setActiveRunId(result.run_id);
                setActiveFold("all");
              }
              setSelectedId(latestBacktestParentId(result.store) ?? selectedId);
              applyTemplate("optimization");
            })
          }
        >
          <FlaskConical size={16} /> Optimize Holdout
        </button>
        </div>
        </div>

        <button onClick={() => runAction(async () => refresh())}>
          <RefreshCw size={16} /> Refresh
        </button>
      </aside>

      <main>
        <header>
          <div>
            <h1>Research Workbench</h1>
            <p>{workspaceId ? `Workspace ${workspaceId.slice(0, 8)}` : "Starting workspace"}</p>
          </div>
          {busy && <span className="pill">Running</span>}
          {error && <span className="error">{error}</span>}
        </header>

        <section className="grid">
          <div className="panel chart-panel wide">
            <div className="panel-heading">
              <h2>
                <BarChart3 size={18} /> {layoutName}
              </h2>
              <div className="canvas-tools">
                <button onClick={() => addChart("ohlc")}>OHLC</button>
                <button onClick={() => addChart("timeseries")}>Time Series</button>
                <button onClick={() => addChart("scatter2d")}>2D</button>
                <button onClick={() => addChart("scatter3d")}>3D</button>
                <button onClick={() => addChart("table")}>Table</button>
                <button onClick={() => addChart("metrics")}>Metrics</button>
                <button onClick={() => addChart("text")}>Text</button>
                <button onClick={() => addChart("calculator")}>
                  <Calculator size={15} /> Calculator
                </button>
              </div>
            </div>
            <div className="context-bar">
              <label>
                <span>Run</span>
                <select
                  value={activeRunId}
                  onChange={(event) => {
                    setActiveRunId(event.target.value);
                    setActiveFold("all");
                  }}
                >
                  <option value="">Manual / latest fixed datasets</option>
                  {studyRuns.map((run) => (
                    <option key={run.run_id} value={run.run_id}>
                      {run.label} ({run.folds.length || 1} fold{run.folds.length === 1 ? "" : "s"})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Fold</span>
                <select value={activeFold} onChange={(event) => setActiveFold(event.target.value)} disabled={!activeRun && !hasCollectionContext}>
                  <option value="all">All</option>
                  {contextFoldOptions.map((fold) => (
                    <option key={fold} value={String(fold)}>
                      Fold {fold}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Split</span>
                <select value={activeSplit} onChange={(event) => setActiveSplit(event.target.value)} disabled={!activeRun && !hasCollectionContext}>
                  {contextSplitOptions.map((split) => (
                    <option key={split} value={split}>
                      {split[0].toUpperCase() + split.slice(1)}
                    </option>
                  ))}
                </select>
              </label>
              <span className="context-status">
                {activeRun
                  ? `${activeRun.artifacts.length} artifact(s)`
                  : hasCollectionContext
                    ? `${chartContextCollection?.name} · ${filterCollectionLeaves(chartContextLeaves, activeFold, activeSplit).length} member(s)`
                    : "Role-bound charts use latest matching artifacts"}
              </span>
            </div>
            <div className="chart-layout">
              {charts.length === 0 ? (
                <div className="empty">No charts.</div>
              ) : (
                charts.map((chart) => {
                  const resolvedChart = {
                    ...chart,
                    datasetId: resolveChartDatasetId(chart),
                    signalDatasetId: resolveSignalDatasetId(chart),
                  };
                  return (
                    <ChartWidget
                      key={chart.id}
                      chart={resolvedChart}
                      workspaceId={workspaceId}
                      store={store}
                      components={components}
                      signalFrame={signalFrame}
                      activeFold={activeFold}
                      activeSplit={activeSplit}
                      dragging={draggingChartId === chart.id}
                      onDerived={handleDerivedDataset}
                      onError={setError}
                      onConfigure={configureChart}
                      onResize={resizeChart}
                      onDragStart={setDraggingChartId}
                      onDragOver={(event) => event.preventDefault()}
                      onDragEnter={(id) => reorderChart(id)}
                      onDrop={(id) => reorderChart(id, true)}
                      onRemove={removeChart}
                    />
                  );
                })
              )}
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
