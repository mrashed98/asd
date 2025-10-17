"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { searchContent, createTrackedItem, getMovieDownloadUrl, getMovieQualities, getSeriesSeasons, updateTrackingStatus, SearchResult, ContentType, Language } from "@/lib/api";
import { Search, Plus, Download, Link as LinkIcon, CheckCircle, AlertCircle, Loader2, Edit } from "lucide-react";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [contentType, setContentType] = useState<'series' | 'movies' | null>(null);
  const [selectedItem, setSelectedItem] = useState<SearchResult | null>(null);
  const [language, setLanguage] = useState<Language>(Language.ENGLISH);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [jdownloaderConnected, setJdownloaderConnected] = useState<boolean | null>(null);
  const [availableQualities, setAvailableQualities] = useState<string[]>([]);
  const [selectedQuality, setSelectedQuality] = useState<string | null>(null);
  const [downloadLogs, setDownloadLogs] = useState<string[]>([]);
  const [showQualitySelection, setShowQualitySelection] = useState(false);
  const [seriesSeasons, setSeriesSeasons] = useState<number[]>([]);
  const [selectedSeasons, setSelectedSeasons] = useState<number[]>([]);
  const [resolvedSeriesUrl, setResolvedSeriesUrl] = useState<string | null>(null);
  const [isLoadingSeasons, setIsLoadingSeasons] = useState(false);
  const [isUpdatingTracking, setIsUpdatingTracking] = useState(false);
  const queryClient = useQueryClient();

  const { data: results, isLoading, refetch } = useQuery({
    queryKey: ["search", query, contentType],
    queryFn: () => searchContent(query, contentType || undefined),
    enabled: false,
    staleTime: 5 * 60 * 1000, // 5 minutes - consider data fresh for 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes - keep in cache for 10 minutes
    refetchOnWindowFocus: false, // Don't refetch when window regains focus
    refetchOnMount: false, // Don't refetch when component mounts if data exists
  });

  const trackMutation = useMutation({
    mutationFn: (data: {
      title: string;
      type: ContentType;
      language: Language;
      arabseed_url: string;
      poster_url?: string;
    }) => createTrackedItem(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracked"] });
      // Invalidate search cache to show updated tracking status
      queryClient.invalidateQueries({ 
        queryKey: ["search", query, contentType],
        exact: true 
      });
      setSelectedItem(null);
      setDownloadUrl(null);
      setJdownloaderConnected(null);
    },
  });

  const qualitiesMutation = useMutation({
    mutationFn: (arabseedUrl: string) => getMovieQualities(arabseedUrl),
    onSuccess: (data) => {
      setAvailableQualities(data.qualities);
      setSelectedQuality(data.qualities[0] || "1080");
      setShowQualitySelection(true);
      setDownloadLogs([`Found ${data.qualities.length} quality options: ${data.qualities.join(', ')}p`]);
    },
    onError: () => {
      // Fallback to default qualities
      setAvailableQualities(["1080", "720", "480"]);
      setSelectedQuality("1080");
      setShowQualitySelection(true);
      setDownloadLogs(["Using default quality options"]);
    },
  });

  const downloadMovieMutation = useMutation({
    mutationFn: ({ arabseedUrl, quality }: { arabseedUrl: string; quality: string }) => 
      getMovieDownloadUrl(arabseedUrl, quality),
    onSuccess: (data) => {
      setDownloadUrl(data.download_url);
      setJdownloaderConnected(data.jdownloader_connected);
      setDownloadLogs(prev => [...prev, ...data.logs]);
      setShowQualitySelection(false);
    },
    onError: () => {
      setDownloadLogs(prev => [...prev, "✗ Failed to get download URL"]);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length >= 2 && contentType) {
      // Check if we already have cached data for this query
      const cacheKey = ["search", query, contentType];
      const cachedData = queryClient.getQueryData(cacheKey);
      
      if (cachedData) {
        console.log("📦 Using cached search results for:", query, contentType);
        // Data is already available, no need to refetch
        return;
      }
      
      console.log("🔍 Making new search request for:", query, contentType);
      refetch();
    }
  };

  const handleTrack = () => {
    if (selectedItem) {
      // Extend payload to include seasons via any to avoid typing drift
      const payload: any = {
        title: selectedItem.title,
        type: selectedItem.type,
        language,
        // Use the resolved series URL if available (for episodes), otherwise use the original URL
        arabseed_url: resolvedSeriesUrl || selectedItem.arabseed_url,
        poster_url: selectedItem.poster_url,
      };
      if (selectedSeasons.length) {
        payload.extra_metadata = { seasons: selectedSeasons };
      }
      trackMutation.mutate(payload);
    }
  };

  const handleDownloadMovie = () => {
    if (selectedItem && selectedItem.type === ContentType.MOVIE) {
      // First, fetch available qualities
      setDownloadLogs(["Fetching available quality options..."]);
      qualitiesMutation.mutate(selectedItem.arabseed_url);
    }
  };

  const handleConfirmQuality = () => {
    if (selectedItem && selectedQuality) {
      setDownloadLogs(prev => [...prev, `Selected quality: ${selectedQuality}p`, "Starting download URL extraction..."]);
      downloadMovieMutation.mutate({
        arabseedUrl: selectedItem.arabseed_url,
        quality: selectedQuality,
      });
    }
  };

  const handleUpdateTracking = async () => {
    if (!selectedItem) return;
    
    setIsUpdatingTracking(true);
    try {
      // Determine the action based on current state and selected seasons
      let action: 'track' | 'untrack';
      let seasons = selectedItem.type === ContentType.SERIES ? selectedSeasons : undefined;
      
      if (selectedItem.is_tracked) {
        // If currently tracked, check if user wants to untrack all or update seasons
        if (selectedSeasons.length === 0) {
          // User deselected all seasons - untrack completely
          action = 'untrack';
          seasons = [];
        } else {
          // User selected some seasons - update tracking with new selection
          action = 'track';
        }
      } else {
        // If not currently tracked, start tracking with selected seasons
        action = 'track';
      }
      
      await updateTrackingStatus(selectedItem.arabseed_url, seasons, action, selectedItem.title);
      
      // Invalidate search cache to force fresh data on next search
      queryClient.invalidateQueries({ 
        queryKey: ["search", query, contentType],
        exact: true 
      });
      
      // Update the selected item's tracking status
      setSelectedItem({
        ...selectedItem,
        is_tracked: seasons && seasons.length > 0,
        tracked_seasons: seasons || []
      });
      
    } catch (error) {
      console.error('Failed to update tracking:', error);
    } finally {
      setIsUpdatingTracking(false);
    }
  };

  const handleCloseDialog = () => {
    setSelectedItem(null);
    setDownloadUrl(null);
    setJdownloaderConnected(null);
    setAvailableQualities([]);
    setSelectedQuality(null);
    setDownloadLogs([]);
    setShowQualitySelection(false);
    setSeriesSeasons([]);
    setSelectedSeasons([]);
    setResolvedSeriesUrl(null);
    setIsLoadingSeasons(false);
    setIsUpdatingTracking(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Search ArabSeed</h1>
        <p className="text-muted-foreground">
          Search for movies and series to track and download
        </p>
      </div>

      <form onSubmit={handleSearch} className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search for content..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full"
            />
          </div>
          <Button type="submit" disabled={isLoading || !contentType}>
            <Search className="mr-2 h-4 w-4" />
            Search
          </Button>
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium">Content Type</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="contentType"
                value="series"
                checked={contentType === 'series'}
                onChange={(e) => setContentType(e.target.value as 'series')}
                className="w-4 h-4"
              />
              <span className="text-sm">Series</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="contentType"
                value="movies"
                checked={contentType === 'movies'}
                onChange={(e) => setContentType(e.target.value as 'movies')}
                className="w-4 h-4"
              />
              <span className="text-sm">Movies</span>
            </label>
          </div>
          {!contentType && (
            <p className="text-sm text-muted-foreground">
              Please select a content type to search
            </p>
          )}
        </div>
      </form>

      {isLoading && <div className="text-center py-8">Searching...</div>}

      {results && results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">
              {contentType === 'series' ? 'Series Results' : 'Movie Results'}
            </h2>
            <Badge variant="outline">
              {results.length} {results.length === 1 ? 'result' : 'results'}
            </Badge>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.map((result, index) => (
              <Card key={index} className="cursor-pointer hover:shadow-lg transition-all duration-200 hover:scale-[1.02]" onClick={async () => {
                // Reset all dialog state first
                setDownloadUrl(null);
                setJdownloaderConnected(null);
                setAvailableQualities([]);
                setSelectedQuality(null);
                setDownloadLogs([]);
                setShowQualitySelection(false);
                setSeriesSeasons([]);
                setSelectedSeasons([]);
                setIsLoadingSeasons(false);

                setSelectedItem(result);
                
                // Use cached seasons data for series
                if (result.type === ContentType.SERIES) {
                  // Use available_seasons from cached search results
                  if (result.available_seasons && result.available_seasons.length > 0) {
                    console.log("📦 Using cached seasons data:", result.available_seasons);
                    setSeriesSeasons(result.available_seasons);
                    
                    // Initialize selectedSeasons based on current tracking status
                    if (result.is_tracked && result.tracked_seasons && result.tracked_seasons.length > 0) {
                      // If already tracked, start with currently tracked seasons selected
                      setSelectedSeasons(result.tracked_seasons);
                    } else {
                      // If not tracked, default select all available seasons
                      setSelectedSeasons(result.available_seasons);
                    }
                    
                    setResolvedSeriesUrl(result.arabseed_url); // Use the result URL
                  } else {
                    // Fallback: load seasons if not available in cache
                    console.log("🔍 Seasons not in cache, loading from API...");
                    setIsLoadingSeasons(true);
                    try {
                      const { seasons, series_url } = await getSeriesSeasons(result.arabseed_url);
                      // Convert seasons array of objects to array of numbers
                      const seasonNumbers = seasons.map((s: any) => typeof s === 'number' ? s : s.number);
                      setSeriesSeasons(seasonNumbers);
                      
                      // Initialize selectedSeasons based on current tracking status
                      if (result.is_tracked && result.tracked_seasons && result.tracked_seasons.length > 0) {
                        // If already tracked, start with currently tracked seasons selected
                        setSelectedSeasons(result.tracked_seasons);
                      } else {
                        // If not tracked, default select all available seasons
                        setSelectedSeasons(seasonNumbers);
                      }
                      
                      setResolvedSeriesUrl(series_url); // Store the resolved parent series URL
                    } catch (error) {
                      console.error('Failed to load seasons:', error);
                      setSeriesSeasons([]);
                      setSelectedSeasons([]);
                      setResolvedSeriesUrl(null);
                    } finally {
                      setIsLoadingSeasons(false);
                    }
                  }
                }
              }}>
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start gap-2">
                    <CardTitle className="text-lg line-clamp-2 leading-tight">
                      {result.title}
                    </CardTitle>
                    <div className="flex flex-col gap-1 shrink-0">
                      <Badge 
                        variant={result.type === ContentType.SERIES ? "default" : "secondary"}
                      >
                        {result.type === ContentType.SERIES ? '📺' : '🎬'} {result.type}
                      </Badge>
                      {result.is_tracked && (
                        <Badge variant="outline" className="text-xs">
                          ✓ Tracked
                        </Badge>
                      )}
                    </div>
                  </div>
                  {result.badge && (
                    <CardDescription className="text-sm text-muted-foreground">
                      {result.badge}
                    </CardDescription>
                  )}
                  {result.is_tracked && result.tracked_seasons && result.tracked_seasons.length > 0 && (
                    <CardDescription className="text-xs text-green-600">
                      Tracking seasons: {result.tracked_seasons.sort((a,b) => a-b).join(', ')}
                    </CardDescription>
                  )}
                </CardHeader>
                
                {result.poster_url && (
                  <CardContent className="pt-0">
                    <div className="w-full h-48 md:h-56 bg-muted/40 rounded-md flex items-center justify-center overflow-hidden">
                      <img
                        src={result.poster_url}
                        alt={result.title}
                        loading="lazy"
                        className="max-h-full w-auto object-contain"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement;
                          target.style.display = 'none';
                        }}
                      />
                    </div>
                  </CardContent>
                )}
                
                <CardContent className="pt-0">
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>
                      {result.type === ContentType.SERIES ? 'Click to track series' : 'Click to download movie'}
                    </span>
                    <span className="text-xs">
                      {result.type === ContentType.SERIES ? '📺' : '🎬'}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {results && results.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No results found for "{query}"
        </div>
      )}

      <Dialog open={!!selectedItem} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {selectedItem?.title
                .replace(/\s*(الموسم|الحلقة|season|episode)\s*(الأول|الاول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)/gi, '')
                .replace(/\s+/g, ' ')
                .trim()}
            </DialogTitle>
            <DialogDescription>
              {selectedItem?.type === ContentType.MOVIE
                ? selectedItem?.is_tracked 
                  ? "This movie is being tracked"
                  : "Download this movie"
                : selectedItem?.is_tracked
                  ? "This series is being tracked"
                  : "Add this series to your tracked items"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Language selector for series, or quality selector for movies */}
            {selectedItem?.type === ContentType.SERIES ? (
              <div>
                <label className="text-sm font-medium">Language</label>
                <Select value={language} onValueChange={(value) => setLanguage(value as Language)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={Language.ENGLISH}>English</SelectItem>
                    <SelectItem value={Language.ARABIC}>Arabic</SelectItem>
                  </SelectContent>
                </Select>

                {isLoadingSeasons && (
                  <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                    <label className="text-sm font-medium">Seasons to track</label>
                    <div className="flex items-center gap-2 mt-2 text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm">Loading available seasons...</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      This may take a few seconds as we extract season information
                    </p>
                  </div>
                )}

                {!isLoadingSeasons && seriesSeasons.length > 0 && (
                  <div className="mt-4">
                    <label className="text-sm font-medium">
                      Seasons to track
                      {selectedItem?.is_tracked && selectedItem.tracked_seasons && (
                        <span className="text-xs text-green-600 ml-2">
                          (Currently tracking: {selectedItem.tracked_seasons.sort((a,b)=>a-b).join(', ')})
                        </span>
                      )}
                    </label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {seriesSeasons.map((s) => {
                        const active = selectedSeasons.includes(s);
                        const currentlyTracked = selectedItem?.tracked_seasons?.includes(s);
                        return (
                          <button
                            key={s}
                            type="button"
                            onClick={() =>
                              setSelectedSeasons((prev) =>
                                prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
                              )
                            }
                            className={`px-3 py-1 rounded border text-sm ${
                              active 
                                ? 'bg-primary text-primary-foreground' 
                                : currentlyTracked
                                  ? 'bg-green-100 text-green-800 border-green-300'
                                  : 'bg-background'
                            }`}
                          >
                            S{s}
                            {currentlyTracked && !active && ' ✓'}
                          </button>
                        );
                      })}
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Click to toggle. Selected: {selectedSeasons.sort((a,b)=>a-b).join(', ') || 'none'}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <>
                {/* Quality selection for movies */}
                {showQualitySelection && availableQualities.length > 0 && (
                  <div>
                    <label className="text-sm font-medium">Select Quality</label>
                    <Select 
                      value={selectedQuality || ""} 
                      onValueChange={setSelectedQuality}
                      disabled={downloadMovieMutation.isPending}
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
                )}
              </>
            )}

            {/* Logs display for movie download process */}
            {selectedItem?.type === ContentType.MOVIE && downloadLogs.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Download Process</label>
                <div className="bg-slate-950 text-green-400 p-3 rounded-lg font-mono text-xs h-48 overflow-y-auto">
                  {downloadLogs.map((log, index) => (
                    <div key={index} className="mb-1">
                      {log}
                    </div>
                  ))}
                  {downloadMovieMutation.isPending && (
                    <div className="flex items-center gap-2 text-yellow-400">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Processing...
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Download status for movies */}
            {selectedItem?.type === ContentType.MOVIE && downloadUrl && (
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
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              {downloadUrl ? 'Close' : 'Cancel'}
            </Button>
            
            {/* Tracking buttons */}
            {selectedItem?.type === ContentType.SERIES && (
              <Button 
                onClick={handleUpdateTracking} 
                disabled={isUpdatingTracking || selectedSeasons.length === 0}
                variant={selectedItem.is_tracked && selectedSeasons.length === 0 ? "destructive" : "default"}
              >
                {isUpdatingTracking ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Updating...
                  </>
                ) : (() => {
                  // Determine button text based on current state and selection
                  if (!selectedItem.is_tracked) {
                    // Not currently tracked - show "Start Tracking"
                    return (
                      <>
                        <Plus className="mr-2 h-4 w-4" />
                        Start Tracking
                      </>
                    );
                  } else if (selectedSeasons.length === 0) {
                    // Currently tracked but no seasons selected - show "Stop Tracking"
                    return (
                      <>
                        <AlertCircle className="mr-2 h-4 w-4" />
                        Stop Tracking
                      </>
                    );
                  } else {
                    // Currently tracked and seasons selected - show "Update Tracking"
                    const currentTracked = selectedItem.tracked_seasons || [];
                    const isSameSelection = currentTracked.length === selectedSeasons.length && 
                                          currentTracked.every(s => selectedSeasons.includes(s));
                    
                    if (isSameSelection) {
                      return (
                        <>
                          <CheckCircle className="mr-2 h-4 w-4" />
                          No Changes
                        </>
                      );
                    } else {
                      return (
                        <>
                          <Edit className="mr-2 h-4 w-4" />
                          Update Tracking
                        </>
                      );
                    }
                  }
                })()}
              </Button>
            )}
            
            {selectedItem?.type === ContentType.MOVIE && !selectedItem.is_tracked && !downloadUrl && !showQualitySelection && (
              <Button 
                onClick={handleDownloadMovie} 
                disabled={qualitiesMutation.isPending}
              >
                <Download className="mr-2 h-4 w-4" />
                {qualitiesMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  'Start Download'
                )}
              </Button>
            )}
            
            {selectedItem?.type === ContentType.MOVIE && !selectedItem.is_tracked && showQualitySelection && !downloadUrl && (
              <Button 
                onClick={handleConfirmQuality} 
                disabled={downloadMovieMutation.isPending || !selectedQuality}
              >
                {downloadMovieMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Extracting...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Get Download Link
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
