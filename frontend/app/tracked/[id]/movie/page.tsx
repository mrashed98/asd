"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../../components/ui/card";
import { Button } from "../../../../components/ui/button";
import { Badge } from "../../../../components/ui/badge";
import { Input } from "../../../../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../../../../components/ui/select";
import { getTrackedItem, getMovieDownloadUrl, getMovieQualities, ContentType, Language } from "../../../../lib/api";
import { ArrowLeft, Download, Link as LinkIcon, CheckCircle, AlertCircle, Loader2, RefreshCw } from "lucide-react";

export default function MovieDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const queryClient = useQueryClient();
  const itemId = params.id as string;

  const [selectedQuality, setSelectedQuality] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [jdownloaderConnected, setJdownloaderConnected] = useState<boolean | null>(null);
  const [downloadLogs, setDownloadLogs] = useState<string[]>([]);
  const [showQualitySelection, setShowQualitySelection] = useState(false);
  const [availableQualities, setAvailableQualities] = useState<string[]>([]);

  const { data: item, isLoading } = useQuery({
    queryKey: ["tracked-item", itemId],
    queryFn: () => getTrackedItem(parseInt(itemId)),
  });

  const qualitiesMutation = useMutation({
    mutationFn: () => getMovieQualities(item?.arabseed_url || ""),
    onSuccess: (data) => {
      setAvailableQualities(data.qualities);
      setShowQualitySelection(true);
    },
    onError: (error) => {
      console.error("Failed to get qualities:", error);
    },
  });

  const downloadMutation = useMutation({
    mutationFn: ({ url, quality }: { url: string; quality?: string }) => 
      getMovieDownloadUrl(url, quality),
    onSuccess: (data) => {
      setDownloadUrl(data.download_url);
      setJdownloaderConnected(data.jdownloader_connected);
      setDownloadLogs(data.logs || []);
    },
    onError: (error) => {
      console.error("Failed to get download URL:", error);
    },
  });

  const handleGetQualities = () => {
    if (item?.arabseed_url) {
      qualitiesMutation.mutate();
    }
  };

  const handleDownload = () => {
    if (item?.arabseed_url) {
      downloadMutation.mutate({ 
        url: item.arabseed_url,
        quality: selectedQuality || undefined
      });
    }
  };

  const handleConfirmQuality = () => {
    if (item?.arabseed_url && selectedQuality) {
      downloadMutation.mutate({ 
        url: item.arabseed_url,
        quality: selectedQuality
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Loading movie details...</span>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="text-center py-8">
        <h2 className="text-2xl font-semibold mb-2">Movie Not Found</h2>
        <p className="text-muted-foreground mb-4">
          The movie you're looking for doesn't exist or has been removed.
        </p>
        <Button onClick={() => router.push("/tracked")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Tracked Items
        </Button>
      </div>
    );
  }

  if (item.type !== ContentType.MOVIE) {
    return (
      <div className="text-center py-8">
        <h2 className="text-2xl font-semibold mb-2">Invalid Content Type</h2>
        <p className="text-muted-foreground mb-4">
          This item is not a movie. Use the episodes page for series.
        </p>
        <Button onClick={() => router.push("/tracked")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Tracked Items
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => router.push("/tracked")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{item.title}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="secondary">Movie</Badge>
            <Badge variant="outline">{item.language}</Badge>
            {item.monitored && (
              <Badge variant="default" className="bg-green-100 text-green-800">
                <CheckCircle className="mr-1 h-3 w-3" />
                Monitored
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Movie Information */}
      <Card>
        <CardHeader>
          <CardTitle>Movie Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Title</label>
              <p className="text-lg font-semibold">{item.title}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Language</label>
              <p className="text-lg">{item.language}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Status</label>
              <p className="text-lg">{item.monitored ? "Monitored" : "Not Monitored"}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Added</label>
              <p className="text-lg">{new Date(item.created_at).toLocaleDateString()}</p>
            </div>
          </div>

          {item.description && (
            <div>
              <label className="text-sm font-medium text-muted-foreground">Description</label>
              <p className="text-sm mt-1">{item.description}</p>
            </div>
          )}

          {item.poster_url && (
            <div>
              <label className="text-sm font-medium text-muted-foreground">Poster</label>
              <div className="mt-2">
                <img
                  src={item.poster_url}
                  alt={item.title}
                  className="w-32 h-48 object-cover rounded-lg border"
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Download Section */}
      <Card>
        <CardHeader>
          <CardTitle>Download Options</CardTitle>
          <CardDescription>
            Get download links for this movie
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!showQualitySelection && !downloadUrl && (
            <div className="space-y-4">
              <Button 
                onClick={handleGetQualities}
                disabled={qualitiesMutation.isPending}
                className="w-full"
              >
                {qualitiesMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Getting Available Qualities...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Get Download Link
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Quality Selection */}
          {showQualitySelection && availableQualities.length > 0 && !downloadUrl && (
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Select Quality</label>
                <Select 
                  value={selectedQuality || ""} 
                  onValueChange={setSelectedQuality}
                  disabled={downloadMutation.isPending}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select quality" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableQualities.map((quality) => (
                      <SelectItem key={quality} value={quality}>
                        {quality}p
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <Button 
                onClick={handleConfirmQuality}
                disabled={downloadMutation.isPending || !selectedQuality}
                className="w-full"
              >
                {downloadMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Extracting Download Link...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Get Download Link
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Download Status */}
          {downloadUrl && (
            <div className="space-y-3 p-4 bg-muted rounded-lg">
              {jdownloaderConnected ? (
                <div className="flex items-start gap-2 text-green-600">
                  <CheckCircle className="h-5 w-5 mt-0.5" />
                  <div>
                    <p className="font-medium">Added to JDownloader</p>
                    <p className="text-sm text-muted-foreground">
                      The download has been sent to JDownloader successfully
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-2 text-orange-600">
                  <AlertCircle className="h-5 w-5 mt-0.5" />
                  <div>
                    <p className="font-medium">JDownloader Connection Failed</p>
                    <p className="text-sm text-muted-foreground">
                      JDownloader is not available. Use the direct download link below:
                    </p>
                  </div>
                </div>
              )}
              
              <div className="flex items-center gap-2 mt-2">
                <Input 
                  value={downloadUrl} 
                  readOnly 
                  className="flex-1 font-mono text-sm"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(downloadUrl);
                  }}
                >
                  <LinkIcon className="h-4 w-4 mr-1" />
                  Copy
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(downloadUrl, '_blank')}
                >
                  <Download className="h-4 w-4 mr-1" />
                  Open
                </Button>
              </div>
            </div>
          )}

          {/* Download Logs */}
          {downloadLogs.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Download Process</label>
              <div className="bg-slate-950 text-green-400 p-3 rounded-lg font-mono text-xs h-48 overflow-y-auto">
                {downloadLogs.map((log, index) => (
                  <div key={index} className="mb-1">
                    {log}
                  </div>
                ))}
                {downloadMutation.isPending && (
                  <div className="flex items-center gap-2 text-yellow-400">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Processing...
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-4">
        <Button 
          variant="outline" 
          onClick={() => router.push("/tracked")}
          className="flex-1"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Tracked Items
        </Button>
        <Button 
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ["tracked-item", itemId] });
          }}
          variant="outline"
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>
    </div>
  );
}
