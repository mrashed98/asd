"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { getSetting, updateSetting, testJDownloader } from "@/lib/api";
import { Save, TestTube } from "lucide-react";

export default function SettingsPage() {
  const [jdownloaderHost, setJdownloaderHost] = useState("");
  const [jdownloaderPort, setJdownloaderPort] = useState("");
  const [downloadFolder, setDownloadFolder] = useState("");
  const [englishSeriesDir, setEnglishSeriesDir] = useState("");
  const [arabicSeriesDir, setArabicSeriesDir] = useState("");
  const [englishMoviesDir, setEnglishMoviesDir] = useState("");
  const [arabicMoviesDir, setArabicMoviesDir] = useState("");
  const [checkInterval, setCheckInterval] = useState("");

  // Load settings
  const { data: jdHost } = useQuery({
    queryKey: ["setting", "jdownloader_host"],
    queryFn: () => getSetting("jdownloader_host"),
  });

  const { data: jdPort } = useQuery({
    queryKey: ["setting", "jdownloader_port"],
    queryFn: () => getSetting("jdownloader_port"),
  });

  const { data: dlFolder } = useQuery({
    queryKey: ["setting", "download_folder"],
    queryFn: () => getSetting("download_folder"),
  });

  const { data: enSeriesDir } = useQuery({
    queryKey: ["setting", "english_series_dir"],
    queryFn: () => getSetting("english_series_dir"),
  });

  const { data: arSeriesDir } = useQuery({
    queryKey: ["setting", "arabic_series_dir"],
    queryFn: () => getSetting("arabic_series_dir"),
  });

  const { data: enMoviesDir } = useQuery({
    queryKey: ["setting", "english_movies_dir"],
    queryFn: () => getSetting("english_movies_dir"),
  });

  const { data: arMoviesDir } = useQuery({
    queryKey: ["setting", "arabic_movies_dir"],
    queryFn: () => getSetting("arabic_movies_dir"),
  });

  const { data: checkInt } = useQuery({
    queryKey: ["setting", "check_interval_hours"],
    queryFn: () => getSetting("check_interval_hours"),
  });

  useEffect(() => {
    if (jdHost) setJdownloaderHost(jdHost.value);
    if (jdPort) setJdownloaderPort(jdPort.value);
    if (dlFolder) setDownloadFolder(dlFolder.value);
    if (enSeriesDir) setEnglishSeriesDir(enSeriesDir.value);
    if (arSeriesDir) setArabicSeriesDir(arSeriesDir.value);
    if (enMoviesDir) setEnglishMoviesDir(enMoviesDir.value);
    if (arMoviesDir) setArabicMoviesDir(arMoviesDir.value);
    if (checkInt) setCheckInterval(checkInt.value);
  }, [jdHost, jdPort, dlFolder, enSeriesDir, arSeriesDir, enMoviesDir, arMoviesDir, checkInt]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      await updateSetting("jdownloader_host", jdownloaderHost);
      await updateSetting("jdownloader_port", jdownloaderPort);
      await updateSetting("download_folder", downloadFolder);
      await updateSetting("english_series_dir", englishSeriesDir);
      await updateSetting("arabic_series_dir", arabicSeriesDir);
      await updateSetting("english_movies_dir", englishMoviesDir);
      await updateSetting("arabic_movies_dir", arabicMoviesDir);
      await updateSetting("check_interval_hours", checkInterval);
    },
  });

  const testMutation = useMutation({
    mutationFn: testJDownloader,
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Configure directories and JDownloader connection
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>JDownloader Configuration</CardTitle>
          <CardDescription>Configure connection to JDownloader API</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Host</label>
              <Input
                value={jdownloaderHost}
                onChange={(e) => setJdownloaderHost(e.target.value)}
                placeholder="localhost"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Port</label>
              <Input
                value={jdownloaderPort}
                onChange={(e) => setJdownloaderPort(e.target.value)}
                placeholder="3129"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
              <TestTube className="mr-2 h-4 w-4" />
              Test Connection
            </Button>
            {testMutation.data && (
              <Badge variant={testMutation.data.connected ? "default" : "destructive"}>
                {testMutation.data.message}
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Directory Configuration</CardTitle>
          <CardDescription>Set up download and media directories</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Download Folder</label>
            <Input
              value={downloadFolder}
              onChange={(e) => setDownloadFolder(e.target.value)}
              placeholder="/downloads"
            />
            <p className="text-xs text-muted-foreground">
              Where JDownloader saves files
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">English Series Directory</label>
            <Input
              value={englishSeriesDir}
              onChange={(e) => setEnglishSeriesDir(e.target.value)}
              placeholder="/media/english-series"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Arabic Series Directory</label>
            <Input
              value={arabicSeriesDir}
              onChange={(e) => setArabicSeriesDir(e.target.value)}
              placeholder="/media/arabic-series"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">English Movies Directory</label>
            <Input
              value={englishMoviesDir}
              onChange={(e) => setEnglishMoviesDir(e.target.value)}
              placeholder="/media/english-movies"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Arabic Movies Directory</label>
            <Input
              value={arabicMoviesDir}
              onChange={(e) => setArabicMoviesDir(e.target.value)}
              placeholder="/media/arabic-movies"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tracking Configuration</CardTitle>
          <CardDescription>Configure episode checking interval</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Check Interval (hours)</label>
            <Input
              type="number"
              value={checkInterval}
              onChange={(e) => setCheckInterval(e.target.value)}
              placeholder="1"
            />
            <p className="text-xs text-muted-foreground">
              How often to check for new episodes
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="mr-2 h-4 w-4" />
          Save Settings
        </Button>
      </div>

      {saveMutation.isSuccess && (
        <div className="text-sm text-green-600">Settings saved successfully!</div>
      )}
    </div>
  );
}

