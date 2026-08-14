"use client";

import * as React from "react";
import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/shared";

interface MediaItem {
  id: string;
  url: string;
  filename: string;
  uploadedAt: string;
}

export default function AdminMediaLibraryPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadMedia = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await api.adminMedia();
      setItems(res || []);
    } catch (err: any) {
      setItems([]);
      setLoadError(err?.message || "Failed to load media assets from server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMedia();
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);

    try {
      const newMedia = await api.adminMediaUpload(fd);
      setItems((prev) => [newMedia, ...prev]);
    } catch (err: any) {
      alert(err?.message || "Media upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleUpload(e.target.files[0]);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.adminMediaDelete(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (err: any) {
      alert(err?.message || "Failed to delete media file.");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="space-y-8 min-h-[80vh]">
      {/* Header */}
      <div className="border-b border-line pb-4">
        <p className="font-util text-eyebrow text-ink-soft uppercase tracking-wider">
          asset manager
        </p>
        <h1 className="font-display text-h1 font-semibold text-ink mt-1">
          Media Library
        </h1>
      </div>

      {/* Upload Box */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={triggerFileSelect}
        className={`border-2 border-dashed p-8 text-center transition-colors cursor-pointer flex flex-col justify-center items-center space-y-3 ${
          dragActive
            ? "border-accent bg-paper-2"
            : "border-line bg-paper hover:bg-paper-2"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileChange}
          className="hidden"
          accept="image/*,application/pdf"
        />
        <div className="text-xl">
          {uploading ? "⌛" : "📤"}
        </div>
        <div>
          <p className="font-display text-body font-medium text-ink">
            {uploading ? "Uploading file asset..." : "Drag files here, or click to browse"}
          </p>
          <p className="font-util text-[10px] text-ink-soft uppercase tracking-wider mt-1">
            Supports PNG, JPG, WEBP, and PDF files
          </p>
        </div>
      </div>

      {/* Media Grid */}
      <section className="space-y-4">
        <h2 className="font-display text-h3 font-medium text-ink">
          Uploaded Assets
        </h2>

        {loadError ? (
          <ErrorState title="Failed to Load Media Library" message={loadError} onRetry={loadMedia} />
        ) : loading ? (
          <div className="p-8 text-center font-display text-xs italic text-ink-soft">
            Querying media records...
          </div>
        ) : items.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {items.map((item) => {
              const isImage = /\.(jpg|jpeg|png|webp|gif)$/i.test(item.filename) || item.url.startsWith("blob:");
              
              return (
                <div
                  key={item.id}
                  className="border border-line bg-paper p-3 flex flex-col justify-between hover:border-ink transition-colors group"
                >
                  {/* Thumbnail / Icon Container */}
                  <div className="aspect-video bg-paper-2 border border-line flex items-center justify-center overflow-hidden relative mb-3">
                    {isImage ? (
                      <img
                        src={item.url}
                        alt={item.filename}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="font-util text-[10px] uppercase tracking-wider text-ink-soft">
                        PDF Document
                      </span>
                    )}
                  </div>

                  {/* Metadata */}
                  <div className="space-y-2">
                    <p className="font-sans text-xs text-ink font-medium truncate" title={item.filename}>
                      {item.filename}
                    </p>
                    <div className="flex justify-between items-center text-[10px] text-ink-soft font-util uppercase tracking-wider">
                      <span>{new Date(item.uploadedAt).toLocaleDateString()}</span>
                      
                      {confirmDeleteId === item.id ? (
                        <div className="text-accent space-x-1.5 font-bold">
                          <button
                            onClick={() => handleDelete(item.id)}
                            className="underline hover:text-ink cursor-pointer"
                          >
                            Yes
                          </button>
                          <span>/</span>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="underline hover:text-ink cursor-pointer"
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDeleteId(item.id)}
                          className="text-accent hover:underline cursor-pointer group-hover:block hidden md:block"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="border border-line p-8 text-center text-ink-soft font-body text-xs italic bg-paper">
            No media files have been uploaded yet.
          </div>
        )}
      </section>
    </div>
  );
}
