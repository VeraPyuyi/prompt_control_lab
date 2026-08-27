import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { fetchDiagnosticCatalog, fetchHistory, fetchOverview, fetchRuns } from "./api";
import { AppShell } from "./components/AppShell";
import { ErrorPanel, LoadingPanel } from "./components/StatePanel";
import { ChangeReviewPage } from "./pages/ChangeReviewPage";
import { AfterPage, BeforePage, DecisionPage, WhyPage } from "./pages/NarrativePages";
import { RunsPage } from "./pages/RunsPage";
import type { Language, ViewId } from "./types";

const HistoryPage = lazy(() => import("./pages/HistoryPage").then((module) => ({ default: module.HistoryPage })));
const StabilityPage = lazy(() => import("./pages/StabilityPage").then((module) => ({ default: module.StabilityPage })));

function Cockpit() {
  const [language, setLanguage] = useState<Language>("en");
  const [overviewLanguage, setOverviewLanguage] = useState<Language | undefined>();
  const languageInitialized = useRef(false);
  const [view, setView] = useState<ViewId>("change-review");
  const [selectedRun, setSelectedRun] = useState(
    () => new URLSearchParams(window.location.search).get("run") ?? "",
  );
  const runs = useQuery({ queryKey: ["runs"], queryFn: fetchRuns, retry: false });
  const overview = useQuery({
    queryKey: ["overview", selectedRun, overviewLanguage],
    queryFn: () => fetchOverview(selectedRun, overviewLanguage),
    enabled: Boolean(selectedRun),
    retry: false,
  });
  const history = useQuery({ queryKey: ["history"], queryFn: fetchHistory, retry: false });
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
    if (!selectedRun) return;
    const url = new URL(window.location.href);
    url.searchParams.set("run", selectedRun);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, [selectedRun]);

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

  function renderView() {
    if (view === "history") {
      if (history.isPending) return <LoadingPanel language={language} />;
      if (history.isError) return <ErrorPanel language={language} onRetry={() => void history.refetch()} />;
      return <Suspense fallback={<LoadingPanel language={language} />}><HistoryPage runs={history.data} language={language} /></Suspense>;
    }
    if (view === "run") {
      if (runs.isPending) return <LoadingPanel language={language} />;
      if (runs.isError) return <ErrorPanel language={language} onRetry={() => void runs.refetch()} />;
      return <RunsPage runs={runs.data} language={language} />;
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
    </AppShell>
  );
}

export function App() {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { refetchOnWindowFocus: false } },
  }));
  return <QueryClientProvider client={queryClient}><Cockpit /></QueryClientProvider>;
}
