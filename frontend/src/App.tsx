import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useRef, useState } from "react";

import {
  fetchCheckpointSeries,
  fetchDiagnosticCatalog,
  fetchHistory,
  fetchOverview,
  fetchRuns,
} from "./api";
import { AppShell } from "./components/AppShell";
import { ErrorPanel, LoadingPanel } from "./components/StatePanel";
import { ChangeReviewPage } from "./pages/ChangeReviewPage";
import { AfterPage, BeforePage, DecisionPage, WhyPage } from "./pages/NarrativePages";
import { RunsPage } from "./pages/RunsPage";
import { ExperimentPage } from "./pages/ExperimentPage";
import { ResearchToolsPage } from "./pages/ResearchToolsPage";
import type { Language, ViewId } from "./types";

const HistoryPage = lazy(() => import("./pages/HistoryPage").then((module) => ({ default: module.HistoryPage })));
const StabilityPage = lazy(() => import("./pages/StabilityPage").then((module) => ({ default: module.StabilityPage })));

function Cockpit() {
  const [language, setLanguage] = useState<Language>("en");
  const [overviewLanguage, setOverviewLanguage] = useState<Language | undefined>();
  const languageInitialized = useRef(false);
  const [view, setView] = useState<ViewId>(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("view");
    if (["experiment", "research", "change-review", "before", "run", "why", "after", "decision", "history", "stability"].includes(requested ?? "")) return requested as ViewId;
    return params.has("run") || params.get("view") === "change-review" ? "change-review" : "experiment";
  });
  const [selectedRun, setSelectedRun] = useState(
    () => new URLSearchParams(window.location.search).get("run") ?? "",
  );
  const [visited, setVisited] = useState({ experiment: view === 'experiment', research: view === 'research' });
  useEffect(() => {
    if (view === 'experiment' || view === 'research') setVisited(previous => ({ ...previous, [view]: true }));
  }, [view]);
  const runs = useQuery({ queryKey: ["runs"], queryFn: fetchRuns, retry: false });
  const overview = useQuery({
    queryKey: ["overview", selectedRun, overviewLanguage],
    queryFn: () => fetchOverview(selectedRun, overviewLanguage),
    enabled: Boolean(selectedRun) || (!runs.isPending && !runs.data?.length),
    retry: false,
  });
  const history = useQuery({ queryKey: ["history"], queryFn: fetchHistory, retry: false });
  const selectedRunSummary = runs.data?.find((run) => run.name === selectedRun);
  const checkpoint = useQuery({
    queryKey: ["checkpoint-series", selectedRun],
    queryFn: () => fetchCheckpointSeries(selectedRun),
    enabled: Boolean(selectedRun && selectedRunSummary?.category === "checkpoint"),
    retry: false,
  });
  const diagnostics = useQuery({
    queryKey: ["diagnostics", selectedRun, language],
    queryFn: () => fetchDiagnosticCatalog(language, selectedRun),
    enabled: Boolean(selectedRun),
    retry: false,
  });

  useEffect(() => {
    if (!runs.data?.length) return;
    const available = new Set(runs.data.map((run) => run.name).filter(Boolean));
    if (selectedRun && available.has(selectedRun)) return;
    const featured = [...runs.data]
      .filter((run) => run.featured && run.name)
      .sort((left, right) => (left.order ?? 10_000) - (right.order ?? 10_000));
    setSelectedRun(featured[0]?.name ?? runs.data[0]?.name ?? "");
  }, [runs.data, selectedRun]);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("view", view);
    if (selectedRun && !["experiment", "research"].includes(view)) url.searchParams.set("run", selectedRun);
    else url.searchParams.delete("run");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, [selectedRun, view]);

  useEffect(() => {
    if (languageInitialized.current || !overview.data?.ui_language) return;
    languageInitialized.current = true;
    setLanguage(overview.data.ui_language);
  }, [overview.data?.ui_language]);

  function changeLanguage(next: Language) {
    languageInitialized.current = true;
    setLanguage(next);
    setOverviewLanguage(next);
  }

  function selectRun(name: string) {
    setSelectedRun(name);
    setOverviewLanguage(language);
    setView("change-review");
  }

  async function checkpointImported(name: string) {
    await Promise.all([runs.refetch(), history.refetch()]);
    setSelectedRun(name);
    setOverviewLanguage(language);
    setView("change-review");
  }

  function renderView() {
    if (view === "experiment" || view === "research") return null;
    if (view === "history") {
      if (history.isPending) return <LoadingPanel language={language} />;
      if (history.isError) return <ErrorPanel language={language} onRetry={() => void history.refetch()} />;
      return <Suspense fallback={<LoadingPanel language={language} />}><HistoryPage runs={history.data} language={language} /></Suspense>;
    }
    if (view === "run") {
      if (runs.isPending) return <LoadingPanel language={language} />;
      if (runs.isError) return <ErrorPanel language={language} onRetry={() => void runs.refetch()} />;
      return (
        <RunsPage
          runs={runs.data}
          language={language}
          onCheckpointImported={checkpointImported}
          checkpointImportEnabled={overview.data?.checkpoint_import_enabled !== false}
        />
      );
    }
    if (view === "stability") {
      if (diagnostics.isPending) return <LoadingPanel language={language} />;
      if (diagnostics.isError) return <ErrorPanel language={language} onRetry={() => void diagnostics.refetch()} />;
      return <Suspense fallback={<LoadingPanel language={language} />}><StabilityPage catalog={diagnostics.data} language={language} /></Suspense>;
    }
    if (overview.isPending) return <LoadingPanel language={language} />;
    if (overview.isError) return <ErrorPanel language={language} onRetry={() => void overview.refetch()} />;
    if (view === "before") return <BeforePage overview={overview.data} language={language} />;
    if (view === "why") return <WhyPage overview={overview.data} language={language} />;
    if (view === "after") return <AfterPage overview={overview.data} language={language} />;
    if (view === "decision") return <DecisionPage overview={overview.data} language={language} />;
    return (
      <ChangeReviewPage
        overview={overview.data}
        language={language}
        cases={(runs.data ?? []).filter((run) => run.featured)}
        selectedRun={selectedRun}
        onSelectRun={selectRun}
        checkpoint={checkpoint.data}
      />
    );
  }

  return (
    <AppShell
      language={language}
      view={view}
      onLanguageChange={changeLanguage}
      onViewChange={setView}
    >
      {renderView()}
      {(visited.experiment || view === 'experiment') && <div hidden={view !== 'experiment'}><ExperimentPage language={language} active={view === 'experiment'} writeEnabled={overview.data?.checkpoint_import_enabled !== false} /></div>}
      {(visited.research || view === 'research') && <div hidden={view !== 'research'}><ResearchToolsPage language={language} writeEnabled={overview.data?.checkpoint_import_enabled !== false} /></div>}
    </AppShell>
  );
}

export function App() {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { refetchOnWindowFocus: false } },
  }));
  return <QueryClientProvider client={queryClient}><Cockpit /></QueryClientProvider>;
}
