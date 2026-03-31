import { Switch, Route, Router as WouterRouter, useLocation } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";
import AppLayout from "@/components/layout/AppLayout";
import ProjectsPage from "@/pages/ProjectsPage";
import NewProjectPage from "@/pages/NewProjectPage";
import PipelinePage from "@/pages/PipelinePage";
import StagePage from "@/pages/StagePage";
import ValidationPage from "@/pages/ValidationPage";
import PreviewPage from "@/pages/PreviewPage";
import ExportPage from "@/pages/ExportPage";
import NotFound from "@/pages/not-found";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 10_000, retry: 1 },
  },
});

function RedirectTo({ to }: { to: string }) {
  const [, navigate] = useLocation();
  useEffect(() => { navigate(to); }, [to, navigate]);
  return null;
}

function Router() {
  return (
    <AppLayout>
      <Switch>
        <Route path="/" component={() => <RedirectTo to="/projects" />} />
        <Route path="/projects" component={ProjectsPage} />
        <Route path="/projects/new" component={NewProjectPage} />
        <Route path="/projects/:id/stage/:stage" component={StagePage} />
        <Route path="/projects/:id/validation" component={ValidationPage} />
        <Route path="/projects/:id/preview" component={PreviewPage} />
        <Route path="/projects/:id/export" component={ExportPage} />
        <Route path="/projects/:id" component={PipelinePage} />
        <Route component={NotFound} />
      </Switch>
    </AppLayout>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <ErrorBoundary>
            <Router />
          </ErrorBoundary>
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
