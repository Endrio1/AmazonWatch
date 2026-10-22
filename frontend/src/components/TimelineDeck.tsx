import React from "react";
import { Play, Pause, SkipBack, SkipForward, Clock } from "lucide-react";

interface TimelineDeckProps {
  timeline: string[];
  currentIndex: number;
  onSelectIndex: (idx: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
}

export const TimelineDeck: React.FC<TimelineDeckProps> = ({
  timeline,
  currentIndex,
  onSelectIndex,
  isPlaying,
  onTogglePlay,
}) => {
  if (timeline.length === 0) return null;

  const currentTimeStr = timeline[currentIndex] || "";
  const currentDate = currentTimeStr ? new Date(currentTimeStr) : null;

  const formatUtc = (d: Date | null) => {
    if (!d) return "—";
    return d.toISOString().replace("T", " ").substring(0, 16) + " UTC";
  };

  const formatLocal = (d: Date | null) => {
    if (!d) return "—";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const getRelativeTime = (d: Date | null) => {
    if (!d) return "";
    const diffMin = Math.round((Date.now() - d.getTime()) / (60 * 1000));
    if (diffMin <= 10) return "Agora mesmo";
    if (diffMin < 60) return `há ${diffMin} min`;
    const diffH = Math.floor(diffMin / 60);
    return `há ${diffH}h ${diffMin % 60}m`;
  };

  return (
    <div className="timeline-deck">
      <div className="timeline-upper">
        <div className="playback-controls">
          <button
            className="btn-control"
            onClick={() => onSelectIndex(Math.max(0, currentIndex - 1))}
            disabled={currentIndex === 0}
            title="Scan anterior (-10 min)"
          >
            <SkipBack size={16} />
          </button>

          <button
            className="btn-play"
            onClick={onTogglePlay}
            title={isPlaying ? "Pausar linha do tempo" : "Reproduzir linha do tempo"}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: 2 }} />}
          </button>

          <button
            className="btn-control"
            onClick={() => onSelectIndex(Math.min(timeline.length - 1, currentIndex + 1))}
            disabled={currentIndex >= timeline.length - 1}
            title="Próximo scan (+10 min)"
          >
            <SkipForward size={16} />
          </button>
        </div>

        <div className="timeline-time-display">
          <Clock size={16} color="#38bdf8" />
          <span className="time-stamp-current">{formatUtc(currentDate)}</span>
          <span className="time-relative">{formatLocal(currentDate)} local ({getRelativeTime(currentDate)})</span>
        </div>
      </div>

      <div className="timeline-scrubber-wrap">
        <input
          type="range"
          min={0}
          max={timeline.length - 1}
          value={currentIndex}
          onChange={(e) => onSelectIndex(Number(e.target.value))}
          className="timeline-slider"
        />
      </div>
    </div>
  );
};
