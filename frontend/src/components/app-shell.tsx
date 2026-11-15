import type { ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  BarChart3, BriefcaseBusiness, ClipboardCheck, FileText, LayoutDashboard, Plug, Send, Settings, UserRound,
} from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarHeader, SidebarInset,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar,
} from "@/components/ui/sidebar";
import { USE_MOCKS } from "@/api";
import { NotificationBell } from "@/components/notifications/notification-bell";

const NAV = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Jobs", url: "/jobs", icon: BriefcaseBusiness },
  { title: "Pending approvals", url: "/approvals", icon: ClipboardCheck },
  { title: "Applications", url: "/applications", icon: Send },
  { title: "Statistics", url: "/stats", icon: BarChart3 },
  { title: "Profile & evidence", url: "/profile", icon: UserRound },
  { title: "Documents", url: "/documents", icon: FileText },
  { title: "Integrations", url: "/integrations", icon: Plug },
  { title: "Settings", url: "/settings", icon: Settings },
] as const;

function pageTitle(path: string) {
  if (path === "/") return "Dashboard";
  if (path.startsWith("/jobs/")) return "Job details";
  return NAV.find((n) => n.url !== "/" && path.startsWith(n.url))?.title ?? "DuuniScript";
}

function AppSidebar({ path }: { path: string }) {
  const { setOpenMobile } = useSidebar();
  const isActive = (url: string) => (url === "/" ? path === "/" : path === url || path.startsWith(`${url}/`));
  return (
    <Sidebar>
      <SidebarHeader className="px-4 py-5">
        {/* Logo slot: replace with <img src="/brand/duuniscript-logo.png" alt="DuuniScript" /> once added. */}
        <Link to="/" className="font-display text-xl font-semibold tracking-tight text-sidebar-foreground" onClick={() => setOpenMobile(false)}>
          DuuniScript
        </Link>
        <p className="text-xs text-muted-foreground">Your job search, on your computer</p>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <nav aria-label="Main">
              <SidebarMenu>
                {NAV.map((item) => (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton asChild isActive={isActive(item.url)}>
                      <Link to={item.url} onClick={() => setOpenMobile(false)} aria-current={isActive(item.url) ? "page" : undefined}>
                        <item.icon aria-hidden className="size-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  return (
    <SidebarProvider>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2">
        Skip to content
      </a>
      <AppSidebar path={path} />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur-sm">
          <SidebarTrigger aria-label="Toggle navigation" />
          <p className="font-display text-lg font-medium" aria-hidden>{pageTitle(path)}</p>
          <div className="ml-auto flex items-center gap-2">
          {USE_MOCKS && (
            <span className=" rounded-full border border-warning/30 bg-warning-soft px-2.5 py-0.5 text-xs font-medium text-warning" title="Showing synthetic sample data, not your real backend">
              Sample data
            </span>
          )}
            <NotificationBell path={path} />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-medium">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <div className="rounded-lg border border-dashed bg-card px-6 py-10 text-center text-sm text-muted-foreground">
        Not available yet.
      </div>
    </>
  );
}
