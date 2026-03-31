import { ReactNode } from "react";
import AppSidebar from "./AppSidebar";

interface AppLayoutProps {
  children: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <AppSidebar />
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {children}
      </main>
    </div>
  );
}
