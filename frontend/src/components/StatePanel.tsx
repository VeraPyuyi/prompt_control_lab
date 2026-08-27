import { AlertCircle, Database, LoaderCircle } from "lucide-react";

import { copy } from "../i18n";
import type { Language } from "../types";
import { Button, Card, Skeleton } from "./ui";

export function LoadingPanel({ language }: { language: Language }) {
  return (
    <Card className="state-panel" aria-live="polite">
      <LoaderCircle className="spin" aria-hidden="true" />
      <strong>{copy[language].loading}</strong>
      <Skeleton className="state-panel__line" />
      <Skeleton className="state-panel__line state-panel__line--short" />
    </Card>
  );
}

export function ErrorPanel({ language, onRetry }: { language: Language; onRetry: () => void }) {
  const labels = copy[language];
  return (
    <Card className="state-panel" role="alert">
      <AlertCircle aria-hidden="true" />
      <strong>{labels.loadError}</strong>
      <p>{labels.loadErrorHelp}</p>
      <Button onClick={onRetry}>{labels.retry}</Button>
    </Card>
  );
}

export function EmptyPanel({ language }: { language: Language }) {
  const labels = copy[language];
  return (
    <Card className="state-panel">
      <Database aria-hidden="true" />
      <strong>{labels.noData}</strong>
      <p>{labels.noDataHelp}</p>
    </Card>
  );
}
