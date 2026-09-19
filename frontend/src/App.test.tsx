import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const overview = {
  ui_language: "en",
  conclusion: "needs_review",
  change_kind: "prompt_change",
  likely_causes: ["The prompt policy changed", "Model identity is unchanged"],
  risk: "medium",
  evidence_coverage: { prompt: true, model: true, audit: false, tests: true },
  next_action: "Review the missing diff audit before release.",
  observations: ["Candidate score improved by 0.08"],
};

const runs = {
  runs: [
    {
      name: "agent_change_review",
      title: { en: "Agent workflow optimization", zh: "Agent 运行优化" },
      category: "agent",
      decision: "needs_review",
      evidence_level: "real_repeated_runs",
      featured: true,
      order: 1,
      id: "agent_change_review",
      created_at: "2026-08-28T10:00:00Z",
      score: 0.82,
      gate_status: "needs_review",
      risk_level: "medium",
      model: "deepseek-chat",
      provider: "deepseek",
      review_required: true,
    },
    {
      name: "model_change_review",
      title: { en: "Model change review", zh: "模型切换审查" },
      category: "model",
      decision: "needs_review",
      evidence_level: "historical_aggregate",
      featured: true,
      order: 2,
    },
    {
      name: "checkpoint_change_review",
      title: { en: "Checkpoint promotion review", zh: "Checkpoint 发布审查" },
      category: "checkpoint",
      decision: "hold",
      evidence_level: "real_three_seed_pilot",
      featured: true,
      order: 3,
    },
  ],
};

const history = {
  runs: [{
    run_name: "candidate-01",
    mean_score: 0.82,
    gate_status: "needs_review",
    change_decision: "needs_review",
    risk_level: "medium",
    model: { model_id: "deepseek-chat", provider: "deepseek" },
    prompt_identity: { prompt_hash: "sha256:abc" },
    review_required: true,
  }],
};

const catalog = {
  terminal_sensitivity: {
    label: "Long-horizon goal influence",
    technical_name: "Terminal sensitivity",
    purpose: "Checks whether a changed final objective has less influence on earlier decisions as a task grows longer.",
    status: "empirical_only",
    metrics: { decay_rate: 0.24, r_squared: 0.91 },
  },
  green_certificate: {
    label: "Local stability boundary",
    technical_name: "Green certificate",
    purpose: "Checks whether stable directions are separated and boundary constraints remain well conditioned in a local approximation.",
    status: "surrogate_consistent",
    metrics: { hyperbolicity_margin: 0.18, boundary_sigma_min: 0.13 },
  },
  posterior_certificate: {
    label: "Local solution confidence range",
    technical_name: "Posterior certificate",
    purpose: "Estimates whether a verifiable solution exists near the observed result and how large that local range is.",
    status: "certificate_verified",
    metrics: { h: 0.19, existence_radius: 0.32 },
  },
};

const checkpointSeries = {
  schema: "prompt_control_lab.checkpoint_visualization.v1",
  decision: "hold",
  stage_order: ["initial", "mid", "final"],
  seeds: ["0", "1", "2"],
  points: [
    { seed: "0", stage: "initial", checkpoint_id: "seed-0-initial", mean_score: 0.0885 },
    { seed: "0", stage: "mid", checkpoint_id: "seed-0-mid", mean_score: 0.1771 },
    { seed: "0", stage: "final", checkpoint_id: "seed-0-final", mean_score: 0.1875 },
    { seed: "1", stage: "initial", checkpoint_id: "seed-1-initial", mean_score: 0.0885 },
    { seed: "1", stage: "mid", checkpoint_id: "seed-1-mid", mean_score: 0.1563 },
    { seed: "1", stage: "final", checkpoint_id: "seed-1-final", mean_score: 0.1875 },
    { seed: "2", stage: "initial", checkpoint_id: "seed-2-initial", mean_score: 0.0885 },
    { seed: "2", stage: "mid", checkpoint_id: "seed-2-mid", mean_score: 0.2031 },
    { seed: "2", stage: "final", checkpoint_id: "seed-2-final", mean_score: 0.2083 },
  ],
  aggregates: [
    { stage: "initial", mean_score: 0.0885, generation_mismatch: 0.5729, selective_aurc: 0.8712, trajectory_drift: 8.3955 },
    { stage: "mid", mean_score: 0.1788, generation_mismatch: 0.4826, selective_aurc: 0.7071, trajectory_drift: 8.7674 },
    { stage: "final", mean_score: 0.1944, generation_mismatch: 0.4670, selective_aurc: 0.6674, trajectory_drift: 8.8259 },
  ],
  diagnostics: {
    generation_mismatch: { available: true, direction: "lower_is_better", aggregates: [] },
    selective_aurc: { available: true, direction: "lower_is_better", aggregates: [] },
    trajectory_drift: { available: true, direction: "context_dependent", aggregates: [] },
  },
  triggered_checks: [
    { check: "trajectory_stability", impact: "hold", observed_mean: 0.43, threshold: 0.05 },
    { check: "generation_mismatch", impact: "hold", observed_mean: 0.467, threshold: 0.1 },
  ],
  narrative: {
    en: {
      changed: "Checkpoint stage changed from initial to final.",
      observed: "Recorded mean score changed from 0.0885 to 0.1944.",
      meaning: "Training stage is associated with a changed performance and risk profile.",
      boundary: "The aggregate trajectory does not identify a unique causal mechanism.",
      next_action: "Review the recorded gate evidence before promotion.",
    },
    zh: {
      changed: "Checkpoint 阶段从 initial 变为 final。",
      observed: "已记录平均分数从 0.0885 变为 0.1944。",
      meaning: "训练阶段与性能和风险画像的变化存在关联。",
      boundary: "聚合轨迹不能识别唯一的因果机制。",
      next_action: "发布前检查已记录的门禁证据。",
    },
  },
};

beforeEach(() => {
  window.history.replaceState({}, "", "/?view=change-review");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/checkpoint-series")
        ? checkpointSeries
        : url.includes("/api/overview")
        ? url.includes("run=model_change_review")
          ? { ...overview, change_kind: "model_change", observations: ["Model aggregate changed"] }
          : url.includes("run=checkpoint_change_review")
            ? { ...overview, conclusion: "hold", change_kind: "checkpoint_change" }
          : overview
        : url.includes("/api/history")
          ? history
        : url.includes("/api/runs")
          ? runs
          : catalog;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

describe("workflow cockpit", () => {
  it("opens with an actionable change review instead of raw JSON", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Change review" })).toBeInTheDocument();
    expect(screen.getAllByText("Needs review").length).toBeGreaterThan(0);
    expect(screen.getByText("Likely causes")).toBeInTheDocument();
    expect(screen.getByText("Evidence coverage")).toBeInTheDocument();
    expect(screen.getByText("Review the missing diff audit before release.")).toBeInTheDocument();
    expect(screen.queryByText(/\"conclusion\"/)).not.toBeInTheDocument();
  });

  it("shows three featured cases and switches the selected review", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("button", { name: /Agent workflow optimization/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Model change review/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Checkpoint promotion review/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Model change review/ }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/overview?run=model_change_review&language=en",
        expect.any(Object),
      );
      expect(fetch).toHaveBeenCalledWith(
        "/api/diagnostics/catalog?language=en&run=model_change_review",
        expect.any(Object),
      );
    });
    expect(await screen.findByText("Model aggregate changed")).toBeInTheDocument();
    expect(window.location.search).toContain("run=model_change_review");
  });

  it("shows linked checkpoint score, diagnostic, and gate evidence", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Checkpoint promotion review/ }));

    expect(await screen.findByRole("heading", { name: "Checkpoint score by seed" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Generation mismatch" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Selective risk AURC" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Representation trajectory drift" })).toBeInTheDocument();
    expect(screen.getByText("trajectory stability")).toBeInTheDocument();
    expect(screen.getByText("What changed")).toBeInTheDocument();
    expect(screen.getByText("What it cannot prove")).toBeInTheDocument();
  });

  it("imports a checkpoint CSV, refreshes runs, and opens the saved run", async () => {
    const user = userEvent.setup();
    let imported = false;
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/session") return new Response(JSON.stringify({ enabled: true, token: "test-session" }), { status: 200 });
      if (url === "/api/checkpoint-runs" && init?.method === "POST") {
        imported = true;
        return new Response(JSON.stringify({
          run: { name: "uploaded-checkpoints" },
          decision: "insufficient_evidence",
          warnings: ["No gate provenance was imported."],
        }), { status: 201, headers: { "Content-Type": "application/json" } });
      }
      if (url === "/api/runs") {
        return new Response(JSON.stringify(imported ? {
          runs: [...runs.runs, {
            name: "uploaded-checkpoints",
            title: { en: "Uploaded Checkpoints", zh: "Uploaded Checkpoints" },
            category: "checkpoint",
            decision: "insufficient_evidence",
          }],
        } : runs), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      const body = url.includes("/api/checkpoint-series")
        ? { ...checkpointSeries, decision: "insufficient_evidence" }
        : url.includes("/api/history")
          ? history
          : url.includes("/api/overview")
            ? { ...overview, conclusion: "insufficient_evidence", change_kind: "checkpoint_change" }
            : catalog;
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Run" }));
    await user.type(screen.getByRole("textbox", { name: "Run name" }), "Uploaded Checkpoints");
    await user.upload(
      screen.getByLabelText("Checkpoint metrics CSV"),
      new File([
        "seed,stage,checkpoint_id,mean_score\n0,initial,a,0.1\n0,final,b,0.2\n",
      ], "checkpoint_metrics.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: "Import checkpoint run" }));

    expect(await screen.findByRole("heading", { name: "Checkpoint score by seed" })).toBeInTheDocument();
    expect(window.location.search).toContain("run=uploaded-checkpoints");
    expect(fetch).toHaveBeenCalledWith("/api/checkpoint-runs", expect.objectContaining({ method: "POST" }));
  });

  it("hides checkpoint upload when the API disables local writes", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/history")
        ? history
        : url.includes("/api/runs")
          ? runs
          : url.includes("/api/overview")
            ? { ...overview, checkpoint_import_enabled: false }
            : catalog;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Run" }));

    expect(screen.queryByRole("heading", { name: "Import checkpoint metrics" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import checkpoint run" })).not.toBeInTheDocument();
  });

  it("uses plain Chinese diagnostic titles and keeps technical names secondary", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "中文" }));
    await user.click(screen.getByRole("button", { name: "稳定性与可信度" }));

    expect(await screen.findByRole("heading", { name: "最终目标影响" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "局部稳定边界" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "局部解可信范围" })).toBeInTheDocument();
    expect(screen.getByText("技术名称：终端敏感性（Terminal sensitivity）")).toBeInTheDocument();
    expect(screen.getByText(/检查最终奖励或目标改变后/)).toBeInTheDocument();
    expect(screen.getAllByText("当前证据")).toHaveLength(3);
    expect(screen.getAllByText("结果意味着什么")).toHaveLength(3);
    expect(screen.getAllByText("不能证明什么")).toHaveLength(3);
    expect(screen.getAllByText("建议下一步")).toHaveLength(3);
  });

  it("shows a useful error state when the overview cannot be loaded", async () => {
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/history")
        ? history
        : url.includes("/api/runs")
          ? runs
          : url.includes("/api/diagnostics")
            ? catalog
            : null;
      return body
        ? new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        : new Response("unavailable", { status: 503 });
    });
    render(<App />);

    expect(await screen.findByText("Could not load this view")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("loads all public cockpit endpoints", async () => {
    render(<App />);

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
    expect(fetch).toHaveBeenCalledWith(
      "/api/overview?run=agent_change_review",
      expect.any(Object),
    );
    expect(fetch).toHaveBeenCalledWith("/api/runs", expect.any(Object));
    expect(fetch).toHaveBeenCalledWith("/api/history", expect.any(Object));
    expect(fetch).toHaveBeenCalledWith(
      "/api/diagnostics/catalog?language=en&run=agent_change_review",
      expect.any(Object),
    );
  });

  it("uses history data for trends and practical risk filters", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "History" }));
    expect(await screen.findByText("Score trend")).toBeInTheDocument();
    expect(screen.getByText("sha256:abc…")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "High risk only" }));
    expect(await screen.findByText("No data recorded yet")).toBeInTheDocument();
  });
});
