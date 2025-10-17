"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { Button } from "../../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../../components/ui/card";
import { Badge } from "../../../../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../../components/ui/table";
import { getEpisodes, triggerEpisodeDownload, enqueueEpisodeDownloads, getDownloadsForItem, triggerDownloadSync, validateDownloadFiles, DownloadStatus } from "../../../../lib/api";
import { Download, ArrowLeft } from "lucide-react";

export default function EpisodesPage() {
  const params = useParams();
  const router = useRouter();
  const seriesId = parseInt(params.id as string);
  const queryClient = useQueryClient();

  const { data: episodes, isLoading } = useQuery({
    queryKey: ["episodes", seriesId],
    queryFn: () => getEpisodes(seriesId),
  });

  const { data: downloads } = useQuery({
    queryKey: ["downloads", seriesId],
    queryFn: () => getDownloadsForItem(seriesId),
    refetchInterval: 5000,
  });

  const downloadMutation = useMutation({
    mutationFn: triggerEpisodeDownload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["episodes", seriesId] });
      queryClient.invalidateQueries({ queryKey: ["downloads"] });
    },
  });

  const bulkDownloadMutation = useMutation({
    mutationFn: async (episodeIds: number[]) => {
      return enqueueEpisodeDownloads(episodeIds);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["episodes", seriesId] });
      queryClient.invalidateQueries({ queryKey: ["downloads"] });
    },
  });

  const syncMutation = useMutation({
    mutationFn: triggerDownloadSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["downloads", seriesId] });
      queryClient.invalidateQueries({ queryKey: ["episodes", seriesId] });
    },
  });

  const validateMutation = useMutation({
    mutationFn: (downloadId: number) => validateDownloadFiles(downloadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["downloads", seriesId] });
      queryClient.invalidateQueries({ queryKey: ["episodes", seriesId] });
    },
  });

  // Group episodes by season
  const episodesBySeason = episodes?.reduce((acc, episode) => {
    const season = episode.season;
    if (!acc[season]) {
      acc[season] = [];
    }
    acc[season].push(episode);
    return acc;
  }, {} as Record<number, typeof episodes>);

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Tracked Items
        </Button>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Episodes</h1>
            <p className="text-muted-foreground">Manage and download episodes</p>
          </div>
          <div>
            <Button
              onClick={() => {
                const toDownload = (episodes || []).filter((e) => !e.downloaded).map((e) => e.id);
                if (toDownload.length) {
                  bulkDownloadMutation.mutate(toDownload);
                }
              }}
              disabled={bulkDownloadMutation.isPending || !episodes || episodes.every((e) => e.downloaded)}
            >
              <Download className="mr-2 h-4 w-4" />
              Download all
            </Button>
          </div>
        </div>
      </div>

      {isLoading && <div className="text-center py-8">Loading episodes...</div>}

      {episodesBySeason &&
        Object.entries(episodesBySeason)
          .sort(([a], [b]) => parseInt(a) - parseInt(b))
          .map(([season, seasonEpisodes]) => (
            <Card key={season}>
              <CardHeader>
                <CardTitle>Season {season}</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Episode</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {seasonEpisodes
                      .sort((a, b) => a.episode_number - b.episode_number)
                      .map((episode) => (
                        <TableRow key={episode.id}>
                          <TableCell>E{episode.episode_number.toString().padStart(2, "0")}</TableCell>
                          <TableCell>{episode.title || "-"}</TableCell>
                          <TableCell>
                            {episode.downloaded ? (
                              <Badge variant="default">Downloaded</Badge>
                            ) : (
                              <Badge variant="secondary">Not Downloaded</Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {!episode.downloaded && (
                              <Button
                                size="sm"
                                onClick={() => downloadMutation.mutate(episode.id)}
                                disabled={downloadMutation.isPending}
                              >
                                <Download className="mr-2 h-4 w-4" />
                                Download
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}

      {/* Active Downloads for this series */}
      <Card>
        <CardHeader>
          <CardTitle>Active Downloads</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-end mb-3">
            <Button variant="outline" size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              {syncMutation.isPending ? "Syncing..." : "Sync and Organize Now"}
            </Button>
          </div>
          {!downloads || downloads.length === 0 ? (
            <div className="text-sm text-muted-foreground">No downloads for this series.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Info</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {downloads.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell>{d.episode_info || "Movie"}</TableCell>
                    <TableCell>
                      <Badge variant={d.status === DownloadStatus.COMPLETED ? "default" : d.status === DownloadStatus.FAILED ? "destructive" : "secondary"}>
                        {d.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{Math.round(d.progress || 0)}%</TableCell>
                    <TableCell>
                      <Button size="sm" variant="outline" onClick={() => validateMutation.mutate(d.id)} disabled={validateMutation.isPending}>
                        Validate files
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {episodes && episodes.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No episodes found for this series
        </div>
      )}
    </div>
  );
}

