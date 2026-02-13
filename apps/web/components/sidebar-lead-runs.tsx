"use client";

import { DownloadIcon, FileSpreadsheetIcon } from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { useState } from "react";
import useSWR from "swr";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { fetcher } from "@/lib/utils";

type LeadRun = {
  id: string;
  summary: string;
  location: string;
  strategy: string;
  result_count: number;
  file_url?: string;
  created_at: string;
};

type LeadRunDetail = LeadRun & {
  filters?: Record<string, unknown>;
};

export function SidebarLeadRuns() {
  const isExternal = Boolean(process.env.NEXT_PUBLIC_API_URL);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useSWR<LeadRun[]>(
    isExternal ? "/api/lead-runs" : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 }
  );

  const { data: detail } = useSWR<LeadRunDetail>(
    selectedId ? `/api/lead-runs/${selectedId}` : null,
    fetcher,
    { revalidateOnFocus: false }
  );

  if (!isExternal || isLoading || !data?.length) return null;

  return (
    <>
      <SidebarGroup>
        <SidebarGroupLabel>Lead Runs</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            {data.map((run) => (
              <SidebarMenuItem key={run.id}>
                <LeadRunItem run={run} onSelect={() => setSelectedId(run.id)} />
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      <Sheet
        open={!!selectedId}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      >
        <SheetContent side="right">
          {detail ? (
            <>
              <SheetHeader>
                <SheetTitle>
                  {detail.location || detail.summary}
                </SheetTitle>
                <SheetDescription>{detail.summary}</SheetDescription>
              </SheetHeader>

              <div className="mt-6 space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">Results</span>
                    <div className="mt-0.5 font-medium">
                      {detail.result_count} leads
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Strategy</span>
                    <div className="mt-0.5 font-medium">
                      {detail.strategy || "—"}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Date</span>
                    <div className="mt-0.5 font-medium">
                      {formatDate(detail.created_at)}
                    </div>
                  </div>
                </div>

                {detail.filters &&
                  Object.keys(detail.filters).length > 0 && (
                    <div className="text-sm">
                      <span className="text-muted-foreground">Filters</span>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {Object.entries(detail.filters).map(([k, v]) => (
                          <Badge key={k} variant="outline">
                            {k}: {String(v)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
              </div>

              <SheetFooter className="mt-8">
                {detail.file_url && (
                  <Button asChild className="w-full">
                    <a
                      href={detail.file_url}
                      download
                      rel="noopener noreferrer"
                      target="_blank"
                    >
                      <DownloadIcon className="mr-2 size-4" />
                      Download Excel
                    </a>
                  </Button>
                )}
              </SheetFooter>
            </>
          ) : (
            <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
              Loading...
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}

function LeadRunItem({
  run,
  onSelect,
}: {
  run: LeadRun;
  onSelect: () => void;
}) {
  const timeAgo = (() => {
    try {
      return formatDistanceToNow(new Date(run.created_at), {
        addSuffix: true,
      });
    } catch {
      return "";
    }
  })();

  return (
    <button
      className="group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-sidebar-accent"
      onClick={onSelect}
      type="button"
    >
      <FileSpreadsheetIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium">
          {run.location || run.summary}
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>{run.result_count} leads</span>
          {run.strategy && (
            <>
              <span>&middot;</span>
              <span className="truncate">{run.strategy}</span>
            </>
          )}
        </div>
        {timeAgo && (
          <div className="text-xs text-muted-foreground/70">{timeAgo}</div>
        )}
      </div>
      {run.file_url && (
        <a
          className="mt-0.5 shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
          download
          href={run.file_url}
          onClick={(e) => e.stopPropagation()}
          rel="noopener noreferrer"
          target="_blank"
          title="Download Excel"
        >
          <DownloadIcon className="size-3.5" />
        </a>
      )}
    </button>
  );
}

function formatDate(dateStr: string): string {
  try {
    return format(new Date(dateStr), "MMM d, yyyy 'at' h:mm a");
  } catch {
    return dateStr;
  }
}
