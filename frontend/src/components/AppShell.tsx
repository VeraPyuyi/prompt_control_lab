import {
  Activity,
  CheckCircle2,
  Clock3,
  FileSearch,
  History,
  Languages,
  ListChecks,
  PlayCircle,
  ShieldCheck,
} from "lucide-react";
import type { ReactNode } from "react";

import { copy, navItems } from "../i18n";
import type { Language, ViewId } from "../types";
import { cn } from "../lib/utils";
import { Button } from "./ui";

const icons = {
  "change-review": FileSearch,
  before: ShieldCheck,
  run: PlayCircle,
  why: ListChecks,
  after: Activity,
  decision: CheckCircle2,
  history: History,
  stability: Clock3,
};

export function AppShell({
  language,
  view,
  onLanguageChange,
  onViewChange,
  children,
}: {
  language: Language;
  view: ViewId;
  onLanguageChange: (language: Language) => void;
  onViewChange: (view: ViewId) => void;
  children: ReactNode;
}) {
  const labels = copy[language];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">PCL</div>
          <div>
            <strong>{labels.appName}</strong>
            <span>{labels.local}</span>
          </div>
        </div>
        <p className="nav-label">{labels.navigation}</p>
        <nav className="nav-list" aria-label={labels.navigation}>
          {navItems.map((item) => {
            const Icon = icons[item.id];
            const label = item[language];
            return (
              <Button
                className={cn("nav-button", view === item.id && "nav-button--active")}
                key={item.id}
                onClick={() => onViewChange(item.id)}
                aria-current={view === item.id ? "page" : undefined}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
              </Button>
            );
          })}
        </nav>
        <div className="language-switch" aria-label="Language">
          <Languages aria-hidden="true" />
          <Button
            className={cn("language-button", language === "en" && "language-button--active")}
            onClick={() => onLanguageChange("en")}
          >
            EN
          </Button>
          <Button
            className={cn("language-button", language === "zh" && "language-button--active")}
            onClick={() => onLanguageChange("zh")}
          >
            中文
          </Button>
        </div>
      </aside>
      <div className="mobile-toolbar">
        <div className="mobile-toolbar__brand">PCL</div>
        <select
          aria-label={labels.navigation}
          value={view}
          onChange={(event) => onViewChange(event.target.value as ViewId)}
        >
          {navItems.map((item) => (
            <option key={item.id} value={item.id}>
              {item[language]}
            </option>
          ))}
        </select>
        <Button
          aria-label={language === "en" ? "中文（移动端）" : "English (mobile)"}
          onClick={() => onLanguageChange(language === "en" ? "zh" : "en")}
        >
          {language === "en" ? "中文" : "EN"}
        </Button>
      </div>
      <main className="main-content">{children}</main>
    </div>
  );
}
