import { useCallback, useEffect, useRef, useState } from "react";

/**
 * YouTube IFrame Player wrapper.
 * - loads the IFrame API script once
 * - exposes seek/play/pause via ref
 * - reports currentTime back through onTime (throttled to ~1s)
 */
let apiPromise = null;

function loadYouTubeAPI() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (apiPromise) return apiPromise;
  apiPromise = new Promise((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      resolve(window.YT);
    };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    tag.async = true;
    document.head.appendChild(tag);
  });
  return apiPromise;
}

export function VideoPlayer({
  videoId,
  startAt = 0,
  onTime,
  onReady,
  seekRef,
  className = "",
}) {
  const containerRef = useRef(null);
  const playerRef = useRef(null);
  const readyRef = useRef(false);
  const [failed, setFailed] = useState(false);
  const onTimeRef = useRef(onTime);
  onTimeRef.current = onTime;

  const startAtRef = useRef(startAt);
  startAtRef.current = startAt;

  useEffect(() => {
    let cancelled = false;
    readyRef.current = false;

    if (!videoId) {
      setFailed(true);
      return undefined;
    }

    loadYouTubeAPI().then((YT) => {
      if (cancelled || !containerRef.current) return;
      try {
        playerRef.current = new YT.Player(containerRef.current, {
          videoId,
          width: "100%",
          height: "100%",
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1,
            start: Math.floor(startAtRef.current || 0),
          },
          events: {
            onReady: (event) => {
              readyRef.current = true;
              onReady?.(event.target);
            },
            onStateChange: (event) => {
              if (event.data === YT.PlayerState.ENDED)
                onTimeRef.current?.(0, true);
            },
            onError: () => setFailed(true),
          },
        });
      } catch {
        setFailed(true);
      }
    });

    let timer = null;
    const poll = () => {
      const p = playerRef.current;
      if (readyRef.current && p?.getCurrentTime) {
        onTimeRef.current?.(p.getCurrentTime(), false);
      }
      timer = window.setTimeout(poll, 1000);
    };
    poll();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      try {
        playerRef.current?.destroy?.();
      } catch {
        /* player already gone */
      }
      playerRef.current = null;
    };
  }, [videoId]);

  const seek = useCallback((seconds) => {
    const p = playerRef.current;
    if (p?.seekTo) {
      p.seekTo(seconds, true);
      p.playVideo?.();
    }
  }, []);

  // expose seek to the parent (transcript clicks, bookmarks, tutor citations)
  useEffect(() => {
    if (seekRef) seekRef.current = seek;
  }, [seekRef, seek]);

  if (failed) {
    return (
      <div
        className={`grid aspect-video w-full place-items-center rounded-2xl border border-line bg-sunken p-6 text-center ${className}`}
        role="alert"
      >
        <div>
          <p className="font-bold">Video can't be embedded here</p>
          <p className="mt-1 text-sm text-muted">
            YouTube refused the embed (owners often disable it). Open it
            directly instead:
          </p>
          <a
            className="link-underline mt-2 inline-block text-sm font-semibold"
            href={`https://www.youtube.com/watch?v=${videoId}`}
            target="_blank"
            rel="noreferrer"
          >
            Watch on YouTube
          </a>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`relative aspect-video w-full overflow-hidden rounded-2xl border border-line bg-black ${className}`}
    >
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />
    </div>
  );
}

export function usePlayerSeek() {
  const ref = useRef(null);
  return ref;
}
