"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../../components/ui/select";
import { getTrackedItems, deleteTrackedItem, ContentType, triggerEpisodeCheck } from "../../lib/api";
import { Trash2, Eye, RefreshCw } from "lucide-react";

export default function TrackedPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [typeFilter, setTypeFilter] = useState<ContentType | "all">("all");

  const { data: items, isLoading } = useQuery({
    queryKey: ["tracked", typeFilter],
    queryFn: () => (typeFilter === "all" ? getTrackedItems() : getTrackedItems(typeFilter)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTrackedItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracked"] });
    },
  });

  const checkMutation = useMutation({
    mutationFn: triggerEpisodeCheck,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Tracked</h1>
          <p className="text-muted-foreground">Your tracked movies and series</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => checkMutation.mutate()} disabled={checkMutation.isPending}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {checkMutation.isPending ? "Checking..." : "Check new episodes"}
          </Button>
          <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as any)}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Filter" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value={ContentType.SERIES}>Series</SelectItem>
              <SelectItem value={ContentType.MOVIE}>Movies</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading && <div className="text-center py-8">Loading tracked items...</div>}

      {items && items.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <CardTitle className="line-clamp-2">{item.title}</CardTitle>
                <CardDescription className="flex items-center gap-2">
                  <Badge variant="secondary">{item.type}</Badge>
                  {typeof item.downloaded_count === "number" && typeof item.episode_count === "number" && (
                    <span className="text-xs text-muted-foreground">
                      {item.downloaded_count}/{item.episode_count}
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex gap-2">
                {item.type === ContentType.SERIES ? (
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => router.push(`/tracked/${item.id}/episodes`)}
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    Episodes
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => router.push(`/tracked/${item.id}/movie`)}
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    Details
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="destructive"
                  className="flex-1"
                  onClick={() => deleteMutation.mutate(item.id)}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Remove
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {items && items.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No tracked items yet. Search for content to start tracking.
        </div>
      )}
    </div>
  );
}
