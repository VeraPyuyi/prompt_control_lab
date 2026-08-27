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

beforeEach(() => {
  window.history.replaceState({}, "", "/");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/overview")
        ? url.includes("run=model_change_review")
          ? { ...overview, change_kind: "model_change", observations: ["Model aggregate changed"] }
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
