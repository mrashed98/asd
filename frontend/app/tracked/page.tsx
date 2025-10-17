"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getTrackedItems, deleteTrackedItem, ContentType, triggerEpisodeCheck } from "@/lib/api";
import { Trash2, Eye, RefreshCw } from "lucide-react";

export default function TrackedPage() {
  const [typeFilter, setTypeFilter] = useState<ContentType | "all">("all");
  const queryClient = useQueryClient();
  const router = useRouter();

  const { data: items, isLoading } = useQuery({
    queryKey: ["tracked", typeFilter],
    queryFn: () => getTrackedItems(typeFilter === "all" ? undefined : typeFilter),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTrackedItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracked"] });
    },
  });

  const checkMutation = useMutation({
    mutationFn: triggerEpisodeCheck,
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Tracked Items</h1>
          <p className="text-muted-foreground">
            Manage your tracked movies and series
          </p>
        </div>
        <Button onClick={() => checkMutation.mutate()} disabled={checkMutation.isPending}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Check for Updates
        </Button>
      </div>

      <div className="flex gap-4">
        <Select value={typeFilter} onValueChange={(value) => setTypeFilter(value as ContentType | "all")}>
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value={ContentType.SERIES}>Series</SelectItem>
            <SelectItem value={ContentType.MOVIE}>Movies</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading && <div className="text-center py-8">Loading...</div>}

      {items && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg line-clamp-2">{item.title}</CardTitle>
                  <Badge variant={item.type === ContentType.SERIES ? "default" : "secondary"}>
                    {item.type}
                  </Badge>
                </div>
                {item.type === ContentType.SERIES && (
                  <CardDescription>
                    {item.episode_count || 0} episodes • {item.downloaded_count || 0} downloaded
                  </CardDescription>
                )}
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

